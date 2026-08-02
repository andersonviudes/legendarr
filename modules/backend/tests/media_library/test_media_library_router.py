from fastapi.testclient import TestClient
from legendarr_backend.api import create_api_app
from legendarr_backend.arr_services.models import ArrService
from legendarr_backend.database.engine import get_session
from legendarr_backend.media_library.models import Movie, Series


def _seed_movie() -> None:
    with get_session() as session:
        arr_service = ArrService(
            name="radarr", service_type="radarr", host="h", port=1, api_key="k"
        )
        session.add(arr_service)
        session.commit()
        session.refresh(arr_service)
        session.add(
            Movie(
                arr_service_id=arr_service.id,
                arr_id=1,
                title="Foo",
                remote_path="/movies/Foo",
                monitored=True,
                status="released",
                quality_profile_name="Any",
            )
        )
        session.commit()


def _seed_series() -> None:
    with get_session() as session:
        arr_service = ArrService(
            name="sonarr", service_type="sonarr", host="h", port=1, api_key="k"
        )
        session.add(arr_service)
        session.commit()
        session.refresh(arr_service)
        session.add(
            Series(
                arr_service_id=arr_service.id,
                arr_id=7,
                title="Bar",
                remote_path="/tv/Bar",
                monitored=True,
                status="continuing",
                quality_profile_name="Any",
                episode_count=8,
                episode_file_count=8,
            )
        )
        session.commit()


def test_get_movies_returns_empty_list_with_nothing_synced(isolated_database):
    with TestClient(create_api_app()) as client:
        response = client.get("/media/movies")

    assert response.status_code == 200
    assert response.json() == []


def test_get_movies_returns_persisted_movies(isolated_database):
    with TestClient(create_api_app()) as client:
        _seed_movie()
        response = client.get("/media/movies")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["title"] == "Foo"
    assert body[0]["monitored"] is True
    assert body[0]["quality_profile_name"] == "Any"


def test_get_series_returns_persisted_series_with_episode_counts(isolated_database):
    with TestClient(create_api_app()) as client:
        _seed_series()
        response = client.get("/media/series")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["title"] == "Bar"
    assert body[0]["episode_count"] == 8
    assert body[0]["episode_file_count"] == 8
