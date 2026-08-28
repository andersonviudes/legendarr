import httpx
from fastapi.testclient import TestClient
from legendarr_web.app import create_app


def test_wanted_page_returns_ok(stub_backend_client):
    app = create_app()
    stub_backend_client(app)

    with TestClient(app) as client:
        response = client.get("/media/wanted")

    assert response.status_code == 200


def test_wanted_page_renders_empty_state_with_nothing_missing(stub_backend_client):
    app = create_app()
    stub_backend_client(app)

    with TestClient(app) as client:
        response = client.get("/media/wanted")

    assert response.status_code == 200
    assert "Nothing wanted" in response.text


def test_wanted_page_renders_missing_items(stub_backend_client):
    def _handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                {
                    "id": 1,
                    "kind": "movie",
                    "title": "Foo",
                    "poster_url": "https://example.test/foo.jpg",
                    "poster_cached": True,
                    "missing_languages": ["pt-BR"],
                    "missing_files_count": 1,
                }
            ],
        )

    app = create_app()
    stub_backend_client(app, handler=_handler)

    with TestClient(app) as client:
        response = client.get("/media/wanted")

    assert response.status_code == 200
    assert "Foo" in response.text
    assert "pt-BR" in response.text
    assert "/posters/movie_1.jpg" in response.text


def test_wanted_movies_page_filters_out_series(stub_backend_client):
    def _handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                {
                    "id": 1,
                    "kind": "movie",
                    "title": "Foo",
                    "poster_url": None,
                    "missing_languages": ["pt-BR"],
                    "missing_files_count": 1,
                },
                {
                    "id": 2,
                    "kind": "series",
                    "title": "Bar",
                    "poster_url": None,
                    "missing_languages": ["pt-BR"],
                    "missing_files_count": 1,
                },
            ],
        )

    app = create_app()
    stub_backend_client(app, handler=_handler)

    with TestClient(app) as client:
        response = client.get("/media/wanted/movies")

    assert response.status_code == 200
    assert "Foo" in response.text
    assert "Bar" not in response.text


def test_wanted_series_page_filters_out_movies(stub_backend_client):
    def _handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                {
                    "id": 1,
                    "kind": "movie",
                    "title": "Foo",
                    "poster_url": None,
                    "missing_languages": ["pt-BR"],
                    "missing_files_count": 1,
                },
                {
                    "id": 2,
                    "kind": "series",
                    "title": "Bar",
                    "poster_url": None,
                    "missing_languages": ["pt-BR"],
                    "missing_files_count": 1,
                },
            ],
        )

    app = create_app()
    stub_backend_client(app, handler=_handler)

    with TestClient(app) as client:
        response = client.get("/media/wanted/series")

    assert response.status_code == 200
    assert "Bar" in response.text
    assert "Foo" not in response.text
