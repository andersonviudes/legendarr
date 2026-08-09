from fastapi.testclient import TestClient
from legendarr_backend.api import create_api_app
from legendarr_backend.scheduling.scheduler import build_scheduler


def test_trigger_sync_enqueues_adhoc_job():
    app = create_api_app()
    # Not started — a running scheduler would execute and remove this one-off job
    # before the assertion below runs.
    scheduler = build_scheduler()
    app.state.scheduler = scheduler

    with TestClient(app) as client:
        response = client.post("/media/sync")

    assert response.status_code == 202
    assert scheduler.get_job("media_library_sync_manual") is not None


def test_trigger_sync_without_scheduler_returns_503():
    with TestClient(create_api_app()) as client:
        response = client.post("/media/sync")

    assert response.status_code == 503
