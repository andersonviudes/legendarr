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
                    "poster_cached": True,
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
    assert "/posters/movie_1.jpg" in response.text


def _movie_missing_poster_json() -> list[dict]:
    return [
        {
            "id": 1,
            "title": "Foo",
            "monitored": True,
            "status": "released",
            "quality_profile_name": "Any",
            "overview": None,
            "poster_url": "https://example.test/foo.jpg",
            "poster_cached": False,
            "year": 2024,
            "imdb_rating": None,
        }
    ]


def test_movies_page_fetches_an_uncached_poster_on_demand(stub_backend_client):
    """`poster_cached: False` triggers the on-demand fallback (ROADMAP.md 0.20.0): the
    page still ends up showing the locally-served poster, not the raw `poster_url`."""

    def _handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/media/movies/1/poster-cache":
            return httpx.Response(200, json={"cached": True})
        return httpx.Response(200, json=_movie_missing_poster_json())

    app = create_app()
    stub_backend_client(app, handler=_handler)

    with TestClient(app) as client:
        response = client.get("/media/movies")

    assert response.status_code == 200
    assert "/posters/movie_1.jpg" in response.text
    assert "https://example.test/foo.jpg" not in response.text


def test_movies_page_renders_placeholder_when_the_on_demand_fetch_fails(stub_backend_client):
    """No hotlink fallback to `poster_url` when the on-demand fetch itself fails either —
    confirmed decision, see the local-poster-cache plan's Agreed Decisions."""

    def _handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/media/movies/1/poster-cache":
            return httpx.Response(500)
        return httpx.Response(200, json=_movie_missing_poster_json())

    app = create_app()
    stub_backend_client(app, handler=_handler)

    with TestClient(app) as client:
        response = client.get("/media/movies")

    assert response.status_code == 200
    assert "Foo" in response.text
    assert "/posters/movie_1.jpg" not in response.text
    assert "https://example.test/foo.jpg" not in response.text
