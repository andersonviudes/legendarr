import logging
from dataclasses import dataclass
from pathlib import Path

from sqlmodel import Session, select

from legendarr_backend.language_profiles.resolve_effective_profile import (
    resolve_media_file_profile,
)
from legendarr_backend.media_library.models import MediaFile
from legendarr_backend.subtitle_acquisition.manage_acquired_subtitle import (
    get_acquired_subtitle,
    record_acquired_subtitle,
)
from legendarr_backend.subtitle_acquisition.manage_subtitle_blacklist import (
    list_blacklisted_download_ids,
)
from legendarr_backend.subtitle_acquisition.match_score import score_candidate
from legendarr_backend.subtitle_acquisition.models import AcquiredSubtitle
from legendarr_backend.subtitle_acquisition.provider_chain import resolve_subtitle_provider_chain
from legendarr_backend.subtitle_acquisition.providers.base import (
    SubtitleProvider,
    SubtitleSearchResult,
)
from legendarr_backend.subtitle_acquisition.release_filters import passes_release_name_filters
from legendarr_backend.subtitle_acquisition.search_context import resolve_subtitle_search_context
from legendarr_backend.subtitle_discovery.models import Subtitle
from legendarr_backend.subtitle_discovery.scan_media_subtitles import scan_subtitles_for_media_file
from legendarr_backend.subtitle_discovery.scan_video_subtitles import SubtitleOrigin

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class UpgradeResult:
    """Outcome of one `upgrade_subtitle_for_media_file` run. Same non-error,
    common-state shape as `AcquisitionResult` — every `skipped_reason` here is an
    expected outcome the periodic job logs and moves past, not a failure.
    """

    upgraded_language: str | None = None
    skipped_reason: str | None = None


def upgrade_subtitle_for_media_file(
    session: Session, media_file: MediaFile, video_path: Path
) -> UpgradeResult:
    """Re-check the media file's current source-language subtitle against a fresh
    provider search and replace it in place if a strictly better-scoring release is
    now available — the "upgrade/replace" half of ROADMAP.md 0.12.0, called by
    `subtitle_acquisition/jobs.py` for a file `acquire_subtitle_for_media_file` left
    alone because it already had a source subtitle.

    Only a subtitle the system itself acquired via a provider download is eligible —
    found via its `AcquiredSubtitle` metadata row, so a manually uploaded external
    subtitle in a source language is never replaced out from under the user. A
    candidate blacklisted for this media file/language (`manage_subtitle_blacklist`)
    is excluded the same way the automatic acquisition path excludes one.
    """
    profile = resolve_media_file_profile(session, media_file)
    if profile is None:
        logger.info("upgrade skipped: media file %d has no language profile", media_file.id)
        return UpgradeResult(skipped_reason="no_language_profile")
    assert media_file.id is not None

    current = _current_upgradeable_subtitle(session, media_file, profile.source_language_list)
    if current is None:
        return UpgradeResult(skipped_reason="no_upgradeable_subtitle")
    subtitle, metadata = current

    chain = resolve_subtitle_provider_chain(session)
    if not chain:
        logger.info(
            "upgrade skipped: media file %d has no subtitle provider configured", media_file.id
        )
        return UpgradeResult(skipped_reason="no_provider_configured")

    context = resolve_subtitle_search_context(session, media_file, video_path)
    blacklisted = list_blacklisted_download_ids(session, media_file.id, subtitle.language)

    best: SubtitleSearchResult | None = None
    best_provider: SubtitleProvider | None = None
    best_score = metadata.score
    try:
        for provider in chain:
            try:
                candidates = provider.search(
                    context.title,
                    subtitle.language,
                    imdb_id=context.imdb_id,
                    moviehash=context.moviehash,
                    season=context.season_number,
                    episode=context.episode_number,
                    video_path=video_path,
                    tvdb_id=context.tvdb_id,
                )
            except Exception:
                logger.warning(
                    "subtitle provider %r failed searching %r (%s), trying next",
                    provider.name,
                    context.title,
                    subtitle.language,
                )
                continue
            for candidate in candidates:
                if not passes_release_name_filters(
                    candidate.release_name,
                    profile.must_contain_terms,
                    profile.must_not_contain_terms,
                ):
                    continue
                if (provider.name, candidate.download_id) in blacklisted:
                    continue
                score = score_candidate(candidate, video_path.stem)
                if score > best_score:
                    best, best_provider, best_score = candidate, provider, score

        if best is None or best_provider is None:
            return UpgradeResult(skipped_reason="no_upgrade_found")

        content = best_provider.download(best)
    finally:
        for provider in chain:
            close = getattr(provider, "close", None)
            if close is not None:
                close()

    output_path = video_path.with_name(f"{video_path.stem}.{subtitle.language}.srt")
    output_path.write_text(content, encoding="utf-8")
    scan_subtitles_for_media_file(session, media_file, video_path)
    record_acquired_subtitle(
        session,
        media_file.id,
        subtitle.language,
        provider=best_provider.name,
        release_name=best.release_name,
        download_id=best.download_id,
        score=best_score,
    )
    return UpgradeResult(upgraded_language=subtitle.language)


def _current_upgradeable_subtitle(
    session: Session, media_file: MediaFile, source_languages: list[str]
) -> tuple[Subtitle, AcquiredSubtitle] | None:
    """The media file's current external source-language subtitle, only if it carries
    `AcquiredSubtitle` metadata — i.e. the system fetched it from a provider itself.
    `source_languages` priority order, same as `translate_media_file._pick_source_subtitle`,
    though in practice at most one source language ever has a subtitle at a time (see
    `acquire_subtitle_for_media_file._has_source_language_subtitle`).
    """
    for language in source_languages:
        subtitle = session.exec(
            select(Subtitle).where(
                Subtitle.media_file_id == media_file.id,
                Subtitle.origin == SubtitleOrigin.EXTERNAL,
                Subtitle.language == language.lower(),
            )
        ).first()
        if subtitle is None:
            continue
        assert subtitle.id is not None
        metadata = get_acquired_subtitle(session, subtitle.id)
        if metadata is not None:
            return subtitle, metadata
    return None
