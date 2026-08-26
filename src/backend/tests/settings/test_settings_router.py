import pytest
import yaml
from fastapi.testclient import TestClient
from legendarr_backend.api import create_api_app
from legendarr_backend.config.config_file import AppConfigFile
from legendarr_backend.config.settings import Settings
from legendarr_backend.media_library.jobs import register_scan_job
from legendarr_backend.scheduling.scheduler import build_scheduler
from legendarr_backend.security.secrets import ENCRYPTED_PREFIX
from legendarr_backend.settings import router as settings_router


@pytest.fixture
def api_client(tmp_path, monkeypatch):
    """A TestClient whose settings router reads/writes a `config.yaml` under `tmp_path`."""
    settings = Settings(data_dir=tmp_path, database_url="")
    monkeypatch.setattr(settings_router, "get_settings", lambda: settings)
    return TestClient(create_api_app())


def _get_payload(client: TestClient) -> dict:
    response = client.get("/settings/tasks")
    assert response.status_code == 200
    return response.json()


def test_get_returns_current_task_settings(api_client):
    payload = _get_payload(api_client)

    assert payload["sync_interval_minutes"] == 15
    assert payload["scan_interval_minutes"] == 60
    assert payload["history_poll_interval_minutes"] == 15
    assert payload["scan_retry_attempts"] == 3
    # Bootstrap fields never leak into this endpoint.
    assert "database_url" not in payload
    assert "radarr_api_key" not in payload


def test_put_persists_to_config_yaml(api_client, tmp_path):
    payload = _get_payload(api_client)
    payload["scan_interval_minutes"] = 5
    payload["history_poll_coalesce"] = False

    response = api_client.put("/settings/tasks", json=payload)

    assert response.status_code == 200
    stored = yaml.safe_load((tmp_path / "config.yaml").read_text())
    assert stored["scan_interval_minutes"] == 5
    assert stored["history_poll_coalesce"] is False
    # A later GET reads the file back — values survive a restart.
    assert _get_payload(api_client)["scan_interval_minutes"] == 5


def test_put_keeps_secrets_encrypted_on_disk(tmp_path, monkeypatch):
    settings = Settings(data_dir=tmp_path, database_url="", radarr_api_key="plain-secret")
    monkeypatch.setattr(settings_router, "get_settings", lambda: settings)
    client = TestClient(create_api_app())
    payload = _get_payload(client)
    client.put("/settings/tasks", json=payload)

    stored = (tmp_path / "config.yaml").read_text()
    assert "plain-secret" not in stored
    assert ENCRYPTED_PREFIX in stored


def test_put_reschedules_running_jobs(tmp_path, monkeypatch):
    settings = Settings(data_dir=tmp_path, database_url="")
    monkeypatch.setattr(settings_router, "get_settings", lambda: settings)
    app = create_api_app()
    # Started, like in production (bootstrap lifespan): on a stopped scheduler
    # `replace_existing` is deferred to start(), and get_job returns the stale pending job.
    scheduler = build_scheduler()
    register_scan_job(scheduler, AppConfigFile())
    scheduler.start()
    app.state.scheduler = scheduler
    client = TestClient(app)

    payload = _get_payload(client)
    payload["scan_interval_minutes"] = 5
    response = client.put("/settings/tasks", json=payload)

    try:
        assert response.status_code == 200
        job = scheduler.get_job("media_library_scan_fanout")
        assert job is not None
        assert job.trigger.interval.total_seconds() == 5 * 60
        # The other two interval jobs are (re-)registered too.
        assert scheduler.get_job("media_library_sync") is not None
        assert scheduler.get_job("arr_history_poll") is not None
    finally:
        scheduler.shutdown(wait=False)


def test_put_without_scheduler_still_persists(api_client, tmp_path):
    payload = _get_payload(api_client)
    payload["sync_interval_minutes"] = 45

    response = api_client.put("/settings/tasks", json=payload)

    assert response.status_code == 200
    stored = yaml.safe_load((tmp_path / "config.yaml").read_text())
    assert stored["sync_interval_minutes"] == 45


def test_put_with_invalid_values_returns_422_and_leaves_file_untouched(api_client, tmp_path):
    payload = _get_payload(api_client)
    before = (tmp_path / "config.yaml").read_text()
    payload["scan_interval_minutes"] = 0
    payload["sync_retry_attempts"] = 0

    response = api_client.put("/settings/tasks", json=payload)

    assert response.status_code == 422
    assert (tmp_path / "config.yaml").read_text() == before


def test_get_webhook_settings_returns_default(api_client):
    response = api_client.get("/settings/webhooks")

    assert response.status_code == 200
    assert response.json() == {"public_url": ""}


def test_put_webhook_settings_persists_and_round_trips(api_client, tmp_path):
    response = api_client.put(
        "/settings/webhooks", json={"public_url": "https://legendarr.example.com"}
    )

    assert response.status_code == 200
    assert response.json() == {"public_url": "https://legendarr.example.com"}
    stored = yaml.safe_load((tmp_path / "config.yaml").read_text())
    assert stored["public_url"] == "https://legendarr.example.com"
    # A later GET reads the file back — the value survives a restart.
    assert api_client.get("/settings/webhooks").json() == {
        "public_url": "https://legendarr.example.com"
    }


def test_get_general_settings_returns_default(api_client):
    response = api_client.get("/settings/general")

    assert response.status_code == 200
    assert response.json() == {"ui_locale": "en"}


def test_put_general_settings_persists_and_round_trips(api_client, tmp_path):
    response = api_client.put("/settings/general", json={"ui_locale": "pt-BR"})

    assert response.status_code == 200
    assert response.json() == {"ui_locale": "pt-BR"}
    stored = yaml.safe_load((tmp_path / "config.yaml").read_text())
    assert stored["ui_locale"] == "pt-BR"
    # A later GET reads the file back — the value survives a restart.
    assert api_client.get("/settings/general").json() == {"ui_locale": "pt-BR"}


def test_put_general_settings_rejects_unsupported_locale(api_client, tmp_path):
    api_client.get("/settings/general")
    before = (tmp_path / "config.yaml").read_text()

    response = api_client.put("/settings/general", json={"ui_locale": "fr"})

    assert response.status_code == 422
    assert (tmp_path / "config.yaml").read_text() == before
