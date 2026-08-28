import httpx
from fastapi.testclient import TestClient
from legendarr_web.app import create_app


def test_series_page_returns_ok(stub_backend_client):
    app = create_app()
    stub_backend_client(app)

    with TestClient(app) as client:
        response = client.get("/media/series")

    assert response.status_code == 200


def test_series_page_renders_synced_series_with_episode_ratio(stub_backend_client):
    def _handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                {
                    "id": 1,
                    "title": "Bar",
                    "monitored": True,
                    "status": "continuing",
                    "quality_profile_name": "Any",
                    "overview": None,
                    "poster_url": "https://example.test/bar.jpg",
                    "poster_cached": True,
                    "year": 2024,
                    "imdb_rating": None,
                    "episode_count": 8,
                    "episode_file_count": 8,
                }
            ],
        )

    app = create_app()
    stub_backend_client(app, handler=_handler)

    with TestClient(app) as client:
        response = client.get("/media/series")

    assert response.status_code == 200
    assert "Bar" in response.text
    assert "8 / 8" in response.text
    assert "episode-bar--continuing" in response.text
    assert "/posters/series_1.jpg" in response.text
