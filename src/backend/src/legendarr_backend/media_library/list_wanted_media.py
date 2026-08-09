from collections import defaultdict

from sqlmodel import Session, select

from legendarr_backend.media_library.list_media_library import metadata_by_key, metadata_fields
from legendarr_backend.media_library.models import MediaFile, Movie, Series
from legendarr_backend.media_library.schemas import WantedRead
from legendarr_backend.media_metadata.models import MediaMetadata
from legendarr_backend.subtitle_discovery.list_missing_subtitles import (
    list_missing_target_languages_by_media_file,
)


def list_wanted_media(session: Session) -> list[WantedRead]:
    """Movies/series with at least one file still missing a target language, one row
    per item — the library-wide view behind `/media/wanted` and the dashboard's
    "Missing subtitles" stat card (`ROADMAP.md` 0.4.0).
    """
    missing_by_file_id = list_missing_target_languages_by_media_file(session)
    if not missing_by_file_id:
        return []

    media_files = session.exec(
        select(MediaFile).where(MediaFile.id.in_(missing_by_file_id.keys()))
    ).all()

    missing_languages_by_movie_id: dict[int, set[str]] = defaultdict(set)
    missing_files_by_movie_id: dict[int, int] = defaultdict(int)
    missing_languages_by_series_id: dict[int, set[str]] = defaultdict(set)
    missing_files_by_series_id: dict[int, int] = defaultdict(int)
    for file in media_files:
        missing = missing_by_file_id[file.id]
        if file.movie_id is not None:
            missing_languages_by_movie_id[file.movie_id].update(missing)
            missing_files_by_movie_id[file.movie_id] += 1
        else:
            missing_languages_by_series_id[file.series_id].update(missing)
            missing_files_by_series_id[file.series_id] += 1

    metadata_by_movie_id = metadata_by_key(session, MediaMetadata.movie_id)
    metadata_by_series_id = metadata_by_key(session, MediaMetadata.series_id)

    rows = [
        WantedRead(
            id=movie.id,
            kind="movie",
            title=movie.title,
            poster_url=metadata_fields(metadata_by_movie_id.get(movie.id))["poster_url"],
            missing_languages=sorted(missing_languages_by_movie_id[movie.id]),
            missing_files_count=missing_files_by_movie_id[movie.id],
        )
        for movie in session.exec(
            select(Movie).where(Movie.id.in_(missing_languages_by_movie_id.keys()))
        )
    ]
    rows += [
        WantedRead(
            id=series.id,
            kind="series",
            title=series.title,
            poster_url=metadata_fields(metadata_by_series_id.get(series.id))["poster_url"],
            missing_languages=sorted(missing_languages_by_series_id[series.id]),
            missing_files_count=missing_files_by_series_id[series.id],
        )
        for series in session.exec(
            select(Series).where(Series.id.in_(missing_languages_by_series_id.keys()))
        )
    ]
    rows.sort(key=lambda row: row.title.lower())
    return rows
