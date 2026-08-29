import logging
from datetime import UTC, datetime

from sqlmodel import Session, select

from legendarr_backend.media_library.models import Series
from legendarr_backend.subtitle_acquisition.candidate_evaluation.quality_gate import (
    passes_quality_gate,
)
from legendarr_backend.subtitle_acquisition.models import PendingSubtitle
from legendarr_backend.subtitle_acquisition.provider_chain import resolve_subtitle_provider_chain
from legendarr_backend.subtitle_acquisition.providers.base import SubtitleSearchResult
from legendarr_backend.subtitle_acquisition.search_media_file_subtitle import SubtitleCandidate

logger = logging.getLogger(__name__)


def download_pending_subtitle_candidate(
    session: Session,
    series: Series,
    season_number: int,
    episode_number: int,
    candidate: SubtitleCandidate,
    language: str,
) -> tuple[bool, str]:
    """Download a candidate a user picked from a pending episode's manual search and
    hold it as a `PendingSubtitle` — same provider-resolution/quality-gate contract as
    `download_subtitle_candidate`, but there's no `video_path` to write next to yet, so
    the content is staged instead of written to disk.

    Replaces any `PendingSubtitle` already held for this episode/language — same
    "last download wins" semantics `record_acquired_subtitle` gives a real file.
    """
    assert series.id is not None
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
        for chain_provider in chain:
            close = getattr(chain_provider, "close", None)
            if close is not None:
                close()

    existing = session.exec(
        select(PendingSubtitle).where(
            PendingSubtitle.series_id == series.id,
            PendingSubtitle.season_number == season_number,
            PendingSubtitle.episode_number == episode_number,
            PendingSubtitle.language == language,
        )
    ).first()
    now = datetime.now(UTC)
    if existing is None:
        session.add(
            PendingSubtitle(
                series_id=series.id,
                season_number=season_number,
                episode_number=episode_number,
                language=language,
                filename=f"{language.lower()}.srt",
                content=content.encode("utf-8"),
                provider=candidate.provider,
                release_name=candidate.release_name,
                download_id=candidate.download_id,
                created_at=now,
            )
        )
    else:
        existing.filename = f"{language.lower()}.srt"
        existing.content = content.encode("utf-8")
        existing.provider = candidate.provider
        existing.release_name = candidate.release_name
        existing.download_id = candidate.download_id
        existing.created_at = now
        session.add(existing)

    return (
        True,
        f"Downloaded {language} subtitle from {candidate.provider} (pending {series.title})",
    )
