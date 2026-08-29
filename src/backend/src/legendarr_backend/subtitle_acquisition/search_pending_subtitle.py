import logging

from sqlmodel import Session

from legendarr_backend.media_library.models import Series
from legendarr_backend.scheduling.circuit_breaker import (
    BreakerCategory,
    is_open,
    record_failure,
    record_success,
)
from legendarr_backend.subtitle_acquisition.candidate_evaluation.match_score import score_candidate
from legendarr_backend.subtitle_acquisition.provider_chain import resolve_subtitle_provider_chain
from legendarr_backend.subtitle_acquisition.search_context import SubtitleSearchContext
from legendarr_backend.subtitle_acquisition.search_media_file_subtitle import SubtitleCandidate

logger = logging.getLogger(__name__)


def search_pending_subtitle_candidates(
    session: Session, series: Series, season_number: int, episode_number: int, language: str
) -> list[SubtitleCandidate]:
    """Search every configured provider for `language`, for an episode Sonarr hasn't
    downloaded yet — same "every candidate, best match first" shape as
    `search_media_file_subtitle_candidates`, just without a `MediaFile`/`video_path`
    to derive the search context or score against.

    `moviehash` is always `None` (no file to hash) and the reference filename scoring
    uses to rank candidates is synthesized from the series title and season/episode
    number rather than a real release filename — the same graceful-degradation
    `resolve_subtitle_search_context` already applies when `video_path` doesn't exist
    on disk, just with nothing else to fall back on. No blacklist filtering: entries
    there are keyed by `media_file_id`, which doesn't exist yet either.
    """
    assert series.id is not None
    context = SubtitleSearchContext(
        title=series.title,
        imdb_id=series.imdb_id,
        tvdb_id=series.tvdb_id,
        moviehash=None,
        season_number=season_number,
        episode_number=episode_number,
    )
    reference_filename = f"{series.title} S{season_number:02d}E{episode_number:02d}"
    chain = resolve_subtitle_provider_chain(session)
    candidates: list[SubtitleCandidate] = []
    try:
        for provider in chain:
            if is_open(BreakerCategory.ACQUISITION, provider.name):
                logger.info(
                    "subtitle provider %r circuit open, skipping pending search for %r (%s)",
                    provider.name,
                    context.title,
                    language,
                )
                continue
            try:
                results = provider.search(
                    context.title,
                    language,
                    imdb_id=context.imdb_id,
                    moviehash=context.moviehash,
                    season=context.season_number,
                    episode=context.episode_number,
                    video_path=None,
                    tvdb_id=context.tvdb_id,
                )
                record_success(BreakerCategory.ACQUISITION, provider.name)
            except Exception:
                record_failure(BreakerCategory.ACQUISITION, provider.name)
                logger.warning(
                    "subtitle provider %r failed searching %r (%s), trying next",
                    provider.name,
                    context.title,
                    language,
                )
                continue
            candidates.extend(
                SubtitleCandidate(
                    provider=provider.name,
                    release_name=result.release_name,
                    download_id=result.download_id,
                    language=result.language,
                    page_link=result.page_link,
                    score=score_candidate(result, reference_filename),
                )
                for result in results
            )
    finally:
        for provider in chain:
            close = getattr(provider, "close", None)
            if close is not None:
                close()

    candidates.sort(key=lambda candidate: candidate.score, reverse=True)
    return candidates
