import httpx
from fastapi.testclient import TestClient
from legendarr_web.app import create_app


def test_movies_page_returns_ok(stub_backend_client):
    app = create_app()
    stub_backend_client(app)

    with TestClient(app) as client:
        response = client.get("/media/movies")

    assert response.status_code == 200


def test_movies_page_renders_synced_movies(stub_backend_client):
    def _handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                {
                    "id": 1,
                    "title": "Foo",
                    "monitored": True,
                    "status": "released",
                    "quality_profile_name": "Any",
                    "overview": None,
                    "poster_url": "https://example.test/foo.jpg",
                    "year": 2024,
                    "imdb_rating": None,
                }
            ],
        )

    app = create_app()
    stub_backend_client(app, handler=_handler)

    with TestClient(app) as client:
        response = client.get("/media/movies")

    assert response.status_code == 200
    assert "Foo" in response.text
    assert "Monitored" in response.text
    assert "Any" in response.text
    assert "https://example.test/foo.jpg" in response.text
