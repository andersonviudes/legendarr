import httpx
from fastapi.testclient import TestClient
from legendarr_web.app import create_app


def _logs_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200,
        json=[{"text": "2026-08-09 INFO test line", "level": "INFO"}],
    )


def test_system_page_lists_recent_log_lines(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_logs_handler)

    with TestClient(app) as client:
        response = client.get("/system/")

    assert response.status_code == 200
    assert "test line" in response.text


def test_system_page_shows_empty_state_with_no_logs(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.get("/system/")

    assert response.status_code == 200
    assert "No log lines yet." in response.text


def test_get_logs_partial_forwards_level_filter(stub_backend_client):
    app = create_app()
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json=[])

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.get("/system/logs", params={"level": "ERROR"})

    assert response.status_code == 200
    assert captured["params"]["level"] == "ERROR"
