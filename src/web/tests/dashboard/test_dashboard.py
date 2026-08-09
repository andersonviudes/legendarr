import httpx
from fastapi.testclient import TestClient
from legendarr_web.app import create_app


def test_dashboard_returns_ok(stub_backend_client):
    app = create_app()
    stub_backend_client(app)

    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "legendarr" in response.text


def test_dashboard_shows_missing_subtitles_count(stub_backend_client):
    def _handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/media/wanted":
            return httpx.Response(200, json=[{"id": 1}, {"id": 2}])
        return httpx.Response(200, json=[])

    app = create_app()
    stub_backend_client(app, handler=_handler)

    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert 'href="/media/wanted"' in response.text
    assert "Missing subtitles" in response.text
