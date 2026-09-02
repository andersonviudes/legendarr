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


def test_dashboard_shows_missing_subtitles_count_by_media_type(stub_backend_client):
    def _handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/media/wanted":
            return httpx.Response(
                200, json=[{"id": 1, "kind": "movie"}, {"id": 2, "kind": "series"}]
            )
        return httpx.Response(200, json=[])

    app = create_app()
    stub_backend_client(app, handler=_handler)

    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert 'href="/media/wanted/movies"' in response.text
    assert 'href="/media/wanted/series"' in response.text
    assert "Movies missing subtitles" in response.text
    assert "Series missing subtitles" in response.text


def test_dashboard_shows_provider_status(stub_backend_client):
    def _handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/subtitle-providers/":
            return httpx.Response(200, json=[{"enabled": True}, {"enabled": False}])
        if request.url.path == "/translation-providers/":
            return httpx.Response(200, json=[{"enabled": True}])
        return httpx.Response(200, json=[])

    app = create_app()
    stub_backend_client(app, handler=_handler)

    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "Providers" in response.text
    assert "1/2" in response.text
    assert "1/1" in response.text


def test_dashboard_polls_the_same_running_tasks_endpoint_as_the_tasks_page(stub_backend_client):
    app = create_app()
    stub_backend_client(app)

    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "Live Activity" in response.text
    assert 'id="dashboard-running-tasks"' in response.text
    assert 'hx-get="/system/tasks/running?limit=10"' in response.text
    assert 'hx-trigger="load, every 3s"' in response.text
