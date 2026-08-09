from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from legendarr_backend.api import create_api_app
from legendarr_backend.arr_services.models import ArrService
from legendarr_backend.database.engine import get_session
from legendarr_backend.media_library.models import MediaFile, Movie, Series
from legendarr_backend.scheduling.scheduler import build_scheduler
from sqlmodel import select


@pytest.fixture
def app_with_scheduler(isolated_database):
    app = create_api_app()
    app.state.scheduler = build_scheduler()
    return app


def _seed(arr_id: int = 42, service_type: str = "radarr") -> tuple[int, int]:
    """Create a connection + media row directly in the DB. Returns (service_id, item_id)."""
    with get_session() as session:
        service = ArrService(
            name=service_type,
            service_type=service_type,
            host=service_type,
            port=7878,
            api_key="api-key",
        )
        session.add(service)
        session.commit()
        session.refresh(service)
        model = Movie if service_type == "radarr" else Series
        item = model(arr_service_id=service.id, arr_id=arr_id, title="Foo", remote_path="/m/Foo")
        session.add(item)
        session.commit()
        session.refresh(item)
        return service.id, item.id


def _media_files() -> list[MediaFile]:
    with get_session() as session:
        return list(session.exec(select(MediaFile)).all())


def test_test_event_is_acknowledged_without_side_effects(app_with_scheduler):
    with TestClient(app_with_scheduler) as client:
        service_id, _ = _seed()
        response = client.post(f"/webhooks/arr/{service_id}", json={"eventType": "Test"})

    assert response.status_code == 204
    assert app_with_scheduler.state.scheduler.get_jobs() == []


def test_grab_event_is_ignored(app_with_scheduler):
    with TestClient(app_with_scheduler) as client:
        service_id, _ = _seed()
        response = client.post(f"/webhooks/arr/{service_id}", json={"eventType": "Grab"})

    assert response.status_code == 204
    assert app_with_scheduler.state.scheduler.get_jobs() == []


def test_unknown_connection_returns_404(app_with_scheduler):
    with TestClient(app_with_scheduler) as client:
        response = client.post("/webhooks/arr/999", json={"eventType": "Test"})

    assert response.status_code == 404


def test_missing_scheduler_returns_503(isolated_database):
    with TestClient(create_api_app()) as client:
        response = client.post("/webhooks/arr/1", json={"eventType": "Test"})

    assert response.status_code == 503


def test_download_event_enqueues_scan_for_the_item(app_with_scheduler):
    with TestClient(app_with_scheduler) as client:
        service_id, movie_id = _seed()
        response = client.post(
            f"/webhooks/arr/{service_id}",
            json={"eventType": "Download", "movie": {"id": 42, "path": "/m/Foo"}},
        )

        assert response.status_code == 204
        job = app_with_scheduler.state.scheduler.get_job(f"media_scan:movie:{movie_id}")
        assert job is not None


def test_download_event_for_unknown_item_is_acknowledged_without_enqueue(app_with_scheduler):
    with TestClient(app_with_scheduler) as client:
        service_id, _ = _seed()
        response = client.post(
            f"/webhooks/arr/{service_id}",
            json={"eventType": "Download", "movie": {"id": 777, "path": "/m/Other"}},
        )

    assert response.status_code == 204
    assert app_with_scheduler.state.scheduler.get_jobs() == []


def test_rename_event_updates_remote_path_and_enqueues(app_with_scheduler):
    with TestClient(app_with_scheduler) as client:
        service_id, movie_id = _seed()
        response = client.post(
            f"/webhooks/arr/{service_id}",
            json={"eventType": "Rename", "movie": {"id": 42, "path": "/m/Foo Renamed"}},
        )

        assert response.status_code == 204
        assert (
            app_with_scheduler.state.scheduler.get_job(f"media_scan:movie:{movie_id}") is not None
        )

    with get_session() as session:
        assert session.get(Movie, movie_id).remote_path == "/m/Foo Renamed"


def test_series_delete_event_removes_media_files(app_with_scheduler):
    with TestClient(app_with_scheduler) as client:
        service_id, series_id = _seed(arr_id=7, service_type="sonarr")
        with get_session() as session:
            session.add(
                MediaFile(
                    series_id=series_id,
                    relative_path="Season 01/ep.mkv",
                    size_bytes=1,
                    scanned_at=datetime.now(UTC),
                )
            )
            session.commit()

        response = client.post(
            f"/webhooks/arr/{service_id}",
            json={"eventType": "SeriesDelete", "series": {"id": 7}},
        )

        assert response.status_code == 204

    assert _media_files() == []


def test_sonarr_download_uses_series_payload(app_with_scheduler):
    with TestClient(app_with_scheduler) as client:
        service_id, series_id = _seed(arr_id=7, service_type="sonarr")
        response = client.post(
            f"/webhooks/arr/{service_id}",
            json={"eventType": "Download", "series": {"id": 7, "path": "/s/Foo"}},
        )

        assert response.status_code == 204
        assert (
            app_with_scheduler.state.scheduler.get_job(f"media_scan:series:{series_id}") is not None
        )
