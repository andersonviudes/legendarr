import logging
from pathlib import Path

from sqlmodel import Session

from legendarr_backend.media_library.models import MediaFile
from legendarr_backend.subtitle_acquisition.candidate_evaluation.match_score import (
    evaluate_candidate,
)
from legendarr_backend.subtitle_acquisition.candidate_evaluation.quality_gate import (
    passes_quality_gate,
)
from legendarr_backend.subtitle_acquisition.manage_acquired_subtitle import (
    record_acquired_subtitle,
)
from legendarr_backend.subtitle_acquisition.provider_chain import resolve_subtitle_provider_chain
from legendarr_backend.subtitle_acquisition.providers.base import SubtitleSearchResult
from legendarr_backend.subtitle_acquisition.search_media_file_subtitle import SubtitleCandidate
from legendarr_backend.subtitle_discovery.scan_media_subtitles import scan_subtitles_for_media_file

logger = logging.getLogger(__name__)


def download_subtitle_candidate(
    session: Session,
    media_file: MediaFile,
    video_path: Path,
    candidate: SubtitleCandidate,
    language: str,
) -> tuple[bool, str]:
    """Download the specific candidate a user picked from a manual search and persist
    it next to `video_path`, as an external sidecar in `language` — same naming
    convention `acquire_subtitle_for_media_file` uses, driven by the caller's
    `language` (not `candidate.language`, which is only what the provider itself
    reported and may format a region subtag differently).

    Never raises: a provider that's been disabled/removed since the search happened,
    or one whose download call fails outright, is reported back as `(False, message)`
    the same way `connection_tests.test_connection` tolerates a flaky provider — the
    caller (the web UI) shows it inline instead of a 500.
    """
    assert media_file.id is not None
    chain = resolve_subtitle_provider_chain(session)
    try:
        provider = next((item for item in chain if item.name == candidate.provider), None)
        if provider is None:
            return False, f"Provider '{candidate.provider}' is no longer configured"

        result = SubtitleSearchResult(
            release_name=candidate.release_name,
            download_id=candidate.download_id,
            language=candidate.language,
            page_link=candidate.page_link,
        )
        try:
            content = provider.download(result)
        except Exception:
            logger.warning(
                "subtitle provider %r failed downloading %r",
                candidate.provider,
                candidate.release_name,
            )
            return False, f"Download from {candidate.provider} failed"
        if not passes_quality_gate(content):
            logger.warning(
                "subtitle from %r (%r) failed quality-gate checks",
                candidate.provider,
                candidate.release_name,
            )
            return False, f"Downloaded subtitle from {candidate.provider} failed quality checks"
    finally:
        # Same close-what-needs-closing shape as `acquire_subtitle_for_media_file` —
        # every provider `resolve_subtitle_provider_chain` instantiated gets closed,
        # not just the one actually used.
        for chain_provider in chain:
            close = getattr(chain_provider, "close", None)
            if close is not None:
                close()

    output_path = video_path.with_name(f"{video_path.stem}.{language.lower()}.srt")
    output_path.write_text(content, encoding="utf-8")
    scan_subtitles_for_media_file(session, media_file, video_path)
    # Re-scored against `video_path` rather than trusting `candidate.score` — the
    # candidate came from a search possibly run against a different reference filename
    # (or, for a re-download request, wasn't scored at all — see
    # `SubtitleCandidateDownloadInput`), so this keeps `AcquiredSubtitle.score` directly
    # comparable to what `upgrade_subtitle_for_media_file` recomputes on a later pass.
    record_acquired_subtitle(
        session,
        media_file.id,
        language,
        provider=candidate.provider,
        release_name=candidate.release_name,
        download_id=candidate.download_id,
        evaluation=evaluate_candidate(result, video_path.stem),
    )
    return True, f"Downloaded {language} subtitle from {candidate.provider}"
