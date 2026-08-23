import logging
from dataclasses import dataclass
from pathlib import Path

from sqlmodel import Session, select

from legendarr_backend.language_profiles.resolve_effective_profile import (
    resolve_media_file_profile,
)
from legendarr_backend.media_library.models import MediaFile
from legendarr_backend.subtitle_acquisition.manage_acquired_subtitle import (
    record_acquired_subtitle,
)
from legendarr_backend.subtitle_acquisition.manage_subtitle_blacklist import (
    list_blacklisted_download_ids,
)
from legendarr_backend.subtitle_acquisition.match_score import pick_best_match, score_candidate
from legendarr_backend.subtitle_acquisition.provider_chain import resolve_subtitle_provider_chain
from legendarr_backend.subtitle_acquisition.providers.base import SubtitleProvider
from legendarr_backend.subtitle_acquisition.release_filters import passes_release_name_filters
from legendarr_backend.subtitle_acquisition.search_context import resolve_subtitle_search_context
from legendarr_backend.subtitle_discovery.models import Subtitle
from legendarr_backend.subtitle_discovery.scan_media_subtitles import scan_subtitles_for_media_file

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AcquisitionResult:
    """Outcome of one `acquire_subtitle_for_media_file` run. `skipped_reason` is set
    (and `acquired_language` left `None`) for every expected, non-error outcome — no
    language profile, no provider configured, or nothing cleared the match cutoff.
    `None`/`None` (both fields unset) means a source-language subtitle already existed
    — a genuine no-op, not something worth a reason string. None of these are errors;
    they're common states the job logs and moves past instead of failing.
    """

    acquired_language: str | None = None
    skipped_reason: str | None = None


@dataclass(frozen=True)
class _AcquiredCandidate:
    """The winning candidate `_search_and_download` found, plus everything
    `record_acquired_subtitle` needs to save its provenance for a later upgrade check."""

    content: str
    provider: str
    release_name: str
    download_id: str
    score: float


def acquire_subtitle_for_media_file(
    session: Session, media_file: MediaFile, video_path: Path
) -> AcquisitionResult:
    """Search and download a source-language subtitle for `media_file` when it has
    none yet (external or embedded), in its `LanguageProfile`'s source-language
    priority order, stopping at the first language a configured provider finds an
    above-cutoff match for. Every candidate is first filtered against the profile's
    `must_contain_terms`/`must_not_contain_terms` (`release_filters.py`) before
    scoring — manual search skips both the filter and the cutoff entirely, see
    `search_media_file_subtitle.py`.

    Movies get their search anchored on `Movie.imdb_id` — the precise, single-title
    lookup OpenSubtitles' API is built around. Series get their episode's season/episode
    number instead, via `media_library.locate.resolve_media_file_episode` (a live
    Sonarr lookup, `None` when it can't be resolved) — most providers still ignore it
    and search title-only, so `pick_best_match`'s cutoff is still what keeps a wrong
    episode's subtitle from being accepted for those; TVsubtitles is the first
    provider that actually anchors its search on it.
    `SubtitleProviderConfig.use_hash` (OpenSubtitles' own `moviehash`, computed from
    `video_path` when reachable) applies to either media type. Series also carry
    `Series.tvdb_id` straight through as `tvdb_id` — every provider but Anime Tosho
    ignores it the same way most ignore season/episode.

    This never runs automatically from `translate_media_file` — that unification is
    0.11.0/0.12.0 roadmap work; this is a standalone, explicitly-triggered step (see
    `subtitle_acquisition/jobs.py`).
    """
    profile = resolve_media_file_profile(session, media_file)
    if profile is None:
        logger.info("acquisition skipped: media file %d has no language profile", media_file.id)
        return AcquisitionResult(skipped_reason="no_language_profile")
    assert media_file.id is not None

    if _has_source_language_subtitle(session, media_file, profile.source_language_list):
        return AcquisitionResult()

    chain = resolve_subtitle_provider_chain(session)
    if not chain:
        logger.info(
            "acquisition skipped: media file %d has no subtitle provider configured",
            media_file.id,
        )
        return AcquisitionResult(skipped_reason="no_provider_configured")

    context = resolve_subtitle_search_context(session, media_file, video_path)

    try:
        for language in profile.source_language_list:
            result = _search_and_download(
                session,
                media_file.id,
                chain,
                context.title,
                language,
                context.imdb_id,
                context.moviehash,
                context.season_number,
                context.episode_number,
                video_path,
                context.tvdb_id,
                profile.must_contain_terms,
                profile.must_not_contain_terms,
            )
            if result is None:
                continue
            output_path = video_path.with_name(f"{video_path.stem}.{language.lower()}.srt")
            output_path.write_text(result.content, encoding="utf-8")
            scan_subtitles_for_media_file(session, media_file, video_path)
            record_acquired_subtitle(
                session,
                media_file.id,
                language,
                provider=result.provider,
                release_name=result.release_name,
                download_id=result.download_id,
                score=result.score,
            )
            return AcquisitionResult(acquired_language=language)
    finally:
        # Most providers open/close a client per call; one that instead holds a
        # session for its whole lifetime (Addic7ed, logged-in cookies) exposes
        # `close()` for this — nothing else in the chain's lifecycle calls it.
        for provider in chain:
            close = getattr(provider, "close", None)
            if close is not None:
                close()

    logger.info(
        "acquisition failed: media file %d found no above-cutoff match in any source language",
        media_file.id,
    )
    return AcquisitionResult(skipped_reason="no_match_found")


def _has_source_language_subtitle(
    session: Session, media_file: MediaFile, source_languages: list[str]
) -> bool:
    existing_languages = set(
        session.exec(select(Subtitle.language).where(Subtitle.media_file_id == media_file.id)).all()
    )
    return any(language.lower() in existing_languages for language in source_languages)


def _search_and_download(
    session: Session,
    media_file_id: int,
    chain: list[SubtitleProvider],
    title: str,
    language: str,
    imdb_id: str | None,
    moviehash: str | None,
    season: int | None,
    episode: int | None,
    video_path: Path,
    tvdb_id: int | None,
    must_contain: list[str],
    must_not_contain: list[str],
) -> _AcquiredCandidate | None:
    blacklisted = list_blacklisted_download_ids(session, media_file_id, language)
    for provider in chain:
        try:
            candidates = provider.search(
                title,
                language,
                imdb_id=imdb_id,
                moviehash=moviehash,
                season=season,
                episode=episode,
                video_path=video_path,
                tvdb_id=tvdb_id,
            )
            candidates = [
                candidate
                for candidate in candidates
                if passes_release_name_filters(
                    candidate.release_name, must_contain, must_not_contain
                )
                and (provider.name, candidate.download_id) not in blacklisted
            ]
            best = pick_best_match(candidates, video_path.stem)
            if best is None:
                continue
            content = provider.download(best)
            return _AcquiredCandidate(
                content=content,
                provider=provider.name,
                release_name=best.release_name,
                download_id=best.download_id,
                score=score_candidate(best, video_path.stem),
            )
        except Exception:
            logger.warning(
                "subtitle provider %r failed searching %r (%s), trying next",
                provider.name,
                title,
                language,
            )
    return None
