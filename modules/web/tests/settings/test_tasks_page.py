import json

import httpx
from fastapi.testclient import TestClient
from legendarr_web.app import create_app

_TASK_SETTINGS = {
    "sync_interval_minutes": 15,
    "sync_retry_attempts": 3,
    "sync_retry_delay_seconds": 5.0,
    "sync_max_instances": 1,
    "sync_coalesce": True,
    "scan_interval_minutes": 60,
    "scan_retry_attempts": 3,
    "scan_retry_delay_seconds": 5.0,
    "scan_max_instances": 1,
    "scan_coalesce": True,
    "history_poll_interval_minutes": 15,
    "history_poll_retry_attempts": 3,
    "history_poll_retry_delay_seconds": 5.0,
    "history_poll_max_instances": 1,
    "history_poll_coalesce": True,
}


def _task_settings_handler(request: httpx.Request) -> httpx.Response:
    if request.method == "PUT":
        return httpx.Response(200, json=json.loads(request.content))
    return httpx.Response(200, json=_TASK_SETTINGS)


def test_tasks_page_renders_current_values(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_task_settings_handler)

    with TestClient(app) as client:
        response = client.get("/settings/tasks/")

    assert response.status_code == 200
    body = response.text
    assert "Library sync" in body
    assert "Library scan" in body
    assert "History poll" in body
    assert 'value="60"' in body  # scan_interval_minutes
    assert 'name="history_poll_interval_minutes"' in body


def test_save_task_settings_puts_to_backend_and_redirects_with_toast(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_task_settings_handler)

    with TestClient(app) as client:
        response = client.post(
            "/settings/tasks/",
            data={**_TASK_SETTINGS, "scan_interval_minutes": "5"},
            follow_redirects=False,
        )

    assert response.status_code == 303
    location = response.headers["location"]
    assert location.startswith("/settings/tasks/?")
    assert "Task+settings+saved." in location


def test_save_task_settings_renders_error_on_backend_rejection(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "PUT":
            return httpx.Response(422, json={"detail": "interval must be positive"})
        return httpx.Response(200, json=_TASK_SETTINGS)

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.post(
            "/settings/tasks/",
            data={**_TASK_SETTINGS, "scan_interval_minutes": "0"},
        )

    assert response.status_code == 422
    assert "interval must be positive" in response.text
