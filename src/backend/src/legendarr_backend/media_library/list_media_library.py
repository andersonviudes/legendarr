from sqlmodel import Session, select

from legendarr_backend.media_library.models import Movie, Series
from legendarr_backend.media_library.schemas import MovieRead, SeriesRead
from legendarr_backend.media_metadata.models import MediaMetadata


def list_movies(session: Session) -> list[MovieRead]:
    metadata_by_movie_id = metadata_by_key(session, MediaMetadata.movie_id)
    movies = []
    for movie in session.exec(select(Movie)).all():
        assert movie.id is not None
        movies.append(_movie_read(movie, metadata_by_movie_id.get(movie.id)))
    return movies


def list_series(session: Session) -> list[SeriesRead]:
    metadata_by_series_id = metadata_by_key(session, MediaMetadata.series_id)
    series_list = []
    for item in session.exec(select(Series)).all():
        assert item.id is not None
        series_list.append(_series_read(item, metadata_by_series_id.get(item.id)))
    return series_list


def metadata_by_key(session: Session, key_column) -> dict[int, MediaMetadata]:
    """Prefetch every `MediaMetadata` row keyed by `movie_id`/`series_id`, so each
    item's metadata is a dict lookup instead of a query per row."""
    rows = session.exec(select(MediaMetadata).where(key_column.is_not(None))).all()
    return {getattr(row, key_column.key): row for row in rows}


def metadata_fields(metadata: MediaMetadata | None) -> dict:
    if metadata is None:
        return {
            "overview": None,
            "poster_url": None,
            "poster_cached": False,
            "year": None,
            "imdb_rating": None,
        }
    return {
        "overview": metadata.overview,
        "poster_url": metadata.poster_url,
        "poster_cached": metadata.poster_cached_at is not None,
        "year": metadata.year,
        "imdb_rating": metadata.imdb_rating,
    }


def _movie_read(movie: Movie, metadata: MediaMetadata | None) -> MovieRead:
    assert movie.id is not None
    return MovieRead(
        id=movie.id,
        title=movie.title,
        monitored=movie.monitored,
        status=movie.status,
        quality_profile_name=movie.quality_profile_name,
        **metadata_fields(metadata),
    )


def _series_read(series: Series, metadata: MediaMetadata | None) -> SeriesRead:
    assert series.id is not None
    return SeriesRead(
        id=series.id,
        title=series.title,
        monitored=series.monitored,
        status=series.status,
        quality_profile_name=series.quality_profile_name,
        episode_count=series.episode_count,
        episode_file_count=series.episode_file_count,
        **metadata_fields(metadata),
    )
