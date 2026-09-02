from sqlmodel import Session

from legendarr_backend.media_library.models import Series
from legendarr_backend.subtitle_acquisition.provider_chain import resolve_subtitle_provider_chain
from legendarr_backend.subtitle_acquisition.provider_search import search_providers_concurrently
from legendarr_backend.subtitle_acquisition.search_context import SubtitleSearchContext
from legendarr_backend.subtitle_acquisition.search_media_file_subtitle import SubtitleCandidate


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
        # `imdb_id` stays unset here the same way `resolve_subtitle_search_context` keeps
        # it unset for a series `MediaFile` — several providers (Addic7ed, subdl, Yify)
        # read a set `imdb_id` as "this is a movie search". The show's own id travels as
        # `series_imdb_id` instead, which OpenSubtitles sends as `parent_imdb_id`.
        imdb_id=None,
        series_imdb_id=series.imdb_id,
        tvdb_id=series.tvdb_id,
        moviehash=None,
        season_number=season_number,
        episode_number=episode_number,
    )
    reference_filename = f"{series.title} S{season_number:02d}E{episode_number:02d}"
    chain = resolve_subtitle_provider_chain(session)
    try:
        scored, _, _ = search_providers_concurrently(
            chain,
            context.title,
            language,
            imdb_id=context.imdb_id,
            moviehash=context.moviehash,
            season=context.season_number,
            episode=context.episode_number,
            video_path=None,
            tvdb_id=context.tvdb_id,
            series_imdb_id=context.series_imdb_id,
            reference_filename=reference_filename,
            check_episode_identity=False,
        )
    finally:
        for provider in chain:
            close = getattr(provider, "close", None)
            if close is not None:
                close()

    return [scored_candidate.candidate for scored_candidate in scored]
