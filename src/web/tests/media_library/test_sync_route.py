import httpx
from fastapi.testclient import TestClient
from legendarr_web.app import create_app


def test_sync_route_shows_success_toast_on_202(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/media/sync":
            return httpx.Response(202, json={"status": "enqueued"})
        return httpx.Response(200, json=[])

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.post("/media/sync")

    assert response.status_code == 200
    assert 'data-toast-type="success"' in response.text
    assert "Library sync started." in response.text


def test_sync_route_shows_error_toast_when_backend_unavailable(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/media/sync":
            return httpx.Response(503, json={"detail": "Scheduler is not running"})
        return httpx.Response(200, json=[])

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.post("/media/sync")

    assert response.status_code == 200
    assert 'data-toast-type="error"' in response.text
