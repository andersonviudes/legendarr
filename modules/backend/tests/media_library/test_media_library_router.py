from datetime import UTC, datetime

from fastapi.testclient import TestClient
from legendarr_backend.api import create_api_app
from legendarr_backend.arr_clients.sonarr_client import SonarrClient
from legendarr_backend.arr_services.models import ArrService
from legendarr_backend.database.engine import get_session
from legendarr_backend.media_library.models import MediaFile, Movie, Series
from legendarr_backend.scheduling.scheduler import build_scheduler


def _seed_movie() -> Movie:
    with get_session() as session:
        arr_service = ArrService(
            name="radarr", service_type="radarr", host="h", port=1, api_key="k"
        )
        session.add(arr_service)
        session.commit()
        session.refresh(arr_service)
        movie = Movie(
            arr_service_id=arr_service.id,
            arr_id=1,
            title="Foo",
            remote_path="/movies/Foo",
            monitored=True,
            status="released",
            quality_profile_name="Any",
        )
        session.add(movie)
        session.commit()
        session.refresh(movie)
        return movie


def _seed_series() -> Series:
    with get_session() as session:
        arr_service = ArrService(
            name="sonarr", service_type="sonarr", host="h", port=1, api_key="k"
        )
        session.add(arr_service)
        session.commit()
        session.refresh(arr_service)
        series = Series(
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
        session.add(series)
        session.commit()
        session.refresh(series)
        return series


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


def test_get_movie_returns_404_when_missing(isolated_database):
    with TestClient(create_api_app()) as client:
        response = client.get("/media/movies/1")

    assert response.status_code == 404


def test_get_movie_returns_detail_with_files(isolated_database):
    with TestClient(create_api_app()) as client:
        movie = _seed_movie()
        response = client.get(f"/media/movies/{movie.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Foo"
    assert body["files"] == []
    assert body["missing_subtitles_count"] == 0


def test_get_series_item_returns_404_when_missing(isolated_database):
    with TestClient(create_api_app()) as client:
        response = client.get("/media/series/1")

    assert response.status_code == 404


def test_get_series_item_returns_detail_with_episodes(isolated_database, monkeypatch):
    monkeypatch.setattr(SonarrClient, "list_episodes", lambda self, series_id: [])

    with TestClient(create_api_app()) as client:
        series = _seed_series()
        response = client.get(f"/media/series/{series.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Bar"
    assert body["episodes"] == []


def test_trigger_movie_scan_enqueues_media_and_subtitle_scan(isolated_database):
    app = create_api_app()
    scheduler = build_scheduler()
    app.state.scheduler = scheduler

    with TestClient(app) as client:
        movie = _seed_movie()
        with get_session() as session:
            session.add(
                MediaFile(
                    movie_id=movie.id,
                    relative_path="Foo.mkv",
                    size_bytes=1,
                    scanned_at=datetime.now(UTC),
                )
            )
            session.commit()
        response = client.post(f"/media/movies/{movie.id}/scan")

    assert response.status_code == 202
    assert scheduler.get_job(f"media_scan:movie:{movie.id}") is not None


def test_trigger_movie_scan_without_scheduler_returns_503(isolated_database):
    with TestClient(create_api_app()) as client:
        movie = _seed_movie()
        response = client.post(f"/media/movies/{movie.id}/scan")

    assert response.status_code == 503


def test_trigger_file_translation_enqueues_translation(isolated_database):
    app = create_api_app()
    scheduler = build_scheduler()
    app.state.scheduler = scheduler

    with TestClient(app) as client:
        movie = _seed_movie()
        with get_session() as session:
            media_file = MediaFile(
                movie_id=movie.id,
                relative_path="Foo.mkv",
                size_bytes=1,
                scanned_at=datetime.now(UTC),
            )
            session.add(media_file)
            session.commit()
            session.refresh(media_file)
            media_file_id = media_file.id
        response = client.post(f"/media/files/{media_file_id}/translate")

    assert response.status_code == 202
    assert scheduler.get_job(f"subtitle_translation:{media_file_id}") is not None


def test_trigger_file_translation_returns_404_when_missing(isolated_database):
    app = create_api_app()
    scheduler = build_scheduler()
    app.state.scheduler = scheduler

    with TestClient(app) as client:
        response = client.post("/media/files/1/translate")

    assert response.status_code == 404
