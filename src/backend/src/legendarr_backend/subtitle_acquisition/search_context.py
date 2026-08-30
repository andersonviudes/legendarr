from dataclasses import dataclass
from pathlib import Path

from sqlmodel import Session

from legendarr_backend.media_library.locate import (
    resolve_media_file_episode,
    resolve_media_file_owner,
)
from legendarr_backend.media_library.models import MediaFile, Movie, Series
from legendarr_backend.subtitle_acquisition.opensubtitles_hash import compute_opensubtitles_hash


@dataclass(frozen=True)
class SubtitleSearchContext:
    """The provider-search parameters derivable from a `MediaFile` alone — shared by
    every caller that needs to search for a subtitle for it, automatic or manual.
    """

    title: str
    imdb_id: str | None
    series_imdb_id: str | None
    tvdb_id: int | None
    moviehash: str | None
    season_number: int | None
    episode_number: int | None


def resolve_subtitle_search_context(
    session: Session, media_file: MediaFile, video_path: Path
) -> SubtitleSearchContext:
    """Resolve `media_file`'s owner (`Movie`/`Series`) into the parameters a
    `SubtitleProvider.search` call takes. See `acquire_subtitle_for_media_file` for why
    each field is what it is (imdb_id/tvdb_id/moviehash/season/episode).
    """
    owner = resolve_media_file_owner(session, media_file)
    # Guaranteed non-None here: every caller only reaches this after already confirming
    # `media_file` has a resolvable owner — a language profile or a video path, both of
    # which require it — so this is a second read of a row known to exist, not a real
    # possible-None branch.
    assert owner is not None

    imdb_id = owner.imdb_id if isinstance(owner, Movie) else None
    # `Series.imdb_id` travels separately from `imdb_id` — OpenSubtitles' own API treats
    # `imdb_id` as a direct episode/movie lookup, so a series' id needs the distinct
    # `series_imdb_id` field (sent as `parent_imdb_id`) instead of overloading `imdb_id`,
    # which several other providers (Addic7ed, subdl, Yify) already read as "this is a
    # movie search" on its own.
    series_imdb_id = owner.imdb_id if isinstance(owner, Series) else None
    tvdb_id = owner.tvdb_id if isinstance(owner, Series) else None
    moviehash = compute_opensubtitles_hash(video_path) if video_path.is_file() else None
    episode = resolve_media_file_episode(session, media_file) if isinstance(owner, Series) else None
    season_number = episode.season_number if episode is not None else None
    episode_number = episode.episode_number if episode is not None else None

    return SubtitleSearchContext(
        title=owner.title,
        imdb_id=imdb_id,
        series_imdb_id=series_imdb_id,
        tvdb_id=tvdb_id,
        moviehash=moviehash,
        season_number=season_number,
        episode_number=episode_number,
    )
