from datetime import UTC, datetime

from legendarr_backend.arr_services.models import ArrService
from legendarr_backend.media_library.list_media_library import list_movies, list_series
from legendarr_backend.media_library.models import Movie, Series
from legendarr_backend.media_metadata.models import MediaMetadata


def _seed_arr_service(session, service_type: str) -> ArrService:
    arr_service = ArrService(
        name=service_type, service_type=service_type, host="h", port=1, api_key="k"
    )
    session.add(arr_service)
    session.commit()
    session.refresh(arr_service)
    return arr_service


def test_list_movies_returns_empty_list_with_nothing_synced(in_memory_session):
    assert list_movies(in_memory_session) == []


def test_list_movies_includes_arr_fields_and_no_metadata(in_memory_session):
    arr_service = _seed_arr_service(in_memory_session, "radarr")
    in_memory_session.add(
        Movie(
            arr_service_id=arr_service.id,
            arr_id=1,
            title="Foo",
            remote_path="/movies/Foo",
            monitored=True,
            status="released",
            quality_profile_id=4,
            quality_profile_name="Any",
        )
    )
    in_memory_session.commit()

    movies = list_movies(in_memory_session)

    assert len(movies) == 1
    assert movies[0].title == "Foo"
    assert movies[0].monitored is True
    assert movies[0].status == "released"
    assert movies[0].quality_profile_name == "Any"
    assert movies[0].poster_url is None
    assert movies[0].overview is None


def test_list_movies_joins_media_metadata_by_movie_id(in_memory_session):
    arr_service = _seed_arr_service(in_memory_session, "radarr")
    movie = Movie(arr_service_id=arr_service.id, arr_id=1, title="Foo", remote_path="/p")
    in_memory_session.add(movie)
    in_memory_session.commit()
    in_memory_session.refresh(movie)
    in_memory_session.add(
        MediaMetadata(
            movie_id=movie.id,
            overview="A movie.",
            poster_url="https://example.test/poster.jpg",
            year=2024,
            imdb_rating=7.5,
            fetched_at=datetime.now(UTC),
        )
    )
    in_memory_session.commit()

    movies = list_movies(in_memory_session)

    assert movies[0].overview == "A movie."
    assert movies[0].poster_url == "https://example.test/poster.jpg"
    assert movies[0].year == 2024
    assert movies[0].imdb_rating == 7.5


def test_list_series_includes_episode_counts(in_memory_session):
    arr_service = _seed_arr_service(in_memory_session, "sonarr")
    in_memory_session.add(
        Series(
            arr_service_id=arr_service.id,
            arr_id=7,
            title="Bar",
            remote_path="/tv/Bar",
            monitored=True,
            status="continuing",
            quality_profile_id=4,
            quality_profile_name="Any",
            episode_count=8,
            episode_file_count=8,
        )
    )
    in_memory_session.commit()

    series = list_series(in_memory_session)

    assert len(series) == 1
    assert series[0].episode_count == 8
    assert series[0].episode_file_count == 8
    assert series[0].poster_url is None
