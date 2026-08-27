import httpx
from fastapi.testclient import TestClient
from legendarr_web.app import create_app


def _handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/media/movies":
        return httpx.Response(200, json=[{"id": 1, "title": "The Avengers"}])
    if request.url.path == "/media/series":
        return httpx.Response(200, json=[{"id": 2, "title": "Avenue 5"}])
    raise AssertionError(f"unexpected request: {request.url.path}")


def test_search_matches_movies_and_series_by_title(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_handler)

    with TestClient(app) as client:
        response = client.get("/media/search", params={"q": "aven"})

    assert response.status_code == 200
    assert "The Avengers" in response.text
    assert "Avenue 5" in response.text
    assert 'href="/media/movies/1"' in response.text
    assert 'href="/media/series/2"' in response.text


def test_search_is_case_insensitive(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_handler)

    with TestClient(app) as client:
        response = client.get("/media/search", params={"q": "AVENGERS"})

    assert response.status_code == 200
    assert "The Avengers" in response.text
    assert "Avenue 5" not in response.text


def test_search_with_no_matches_shows_empty_state(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_handler)

    with TestClient(app) as client:
        response = client.get("/media/search", params={"q": "nothing-like-this"})

    assert response.status_code == 200
    assert "No results found." in response.text


def test_search_with_blank_query_returns_nothing(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_handler)

    with TestClient(app) as client:
        response = client.get("/media/search", params={"q": "  "})

    assert response.status_code == 200
    assert response.text.strip() == ""


def test_topbar_renders_the_global_search_input(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_handler)

    with TestClient(app) as client:
        response = client.get("/media/movies")

    assert response.status_code == 200
    assert 'id="global-search-input"' in response.text
    assert 'name="q"' in response.text
    assert 'hx-get="/media/search"' in response.text
