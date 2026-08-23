import httpx
from fastapi.testclient import TestClient
from legendarr_web.app import create_app


def _movie_detail_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "id": 1,
            "title": "Foo",
            "monitored": True,
            "status": "released",
            "quality_profile_name": "Any",
            "overview": None,
            "poster_url": "https://example.test/foo.jpg",
            "year": 2024,
            "imdb_rating": None,
            "remote_path": "/movies/Foo",
            "language_profile_name": "Default",
            "target_languages": ["pt-BR"],
            "missing_subtitles_count": 1,
            "files": [
                {
                    "id": 5,
                    "relative_path": "Foo.mkv",
                    "size_bytes": 100,
                    "subtitles": [{"id": 9, "language": "en", "origin": "external"}],
                }
            ],
        },
    )


def _missing_movie_handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/media/movies/1":
        return httpx.Response(404, json={"detail": "Movie not found"})
    return httpx.Response(200, json=[])


def test_movie_detail_page_renders_files_and_subtitles(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_movie_detail_handler)

    with TestClient(app) as client:
        response = client.get("/media/movies/1")

    assert response.status_code == 200
    assert "Foo" in response.text
    assert "Foo.mkv" in response.text
    assert "en" in response.text
    assert "1 missing subtitles" in response.text
    assert "/media/files/5/translate" in response.text
    assert "/media/subtitles/9/sync-timing" in response.text
    assert "/media/subtitles/9/translate" in response.text
    assert "/media/subtitles/9/blacklist" in response.text


def _movie_detail_with_embedded_subtitle_handler(request: httpx.Request) -> httpx.Response:
    response = _movie_detail_handler(request)
    body = response.json()
    body["files"][0]["subtitles"] = [{"id": 9, "language": "ja", "origin": "embedded"}]
    return httpx.Response(200, json=body)


def test_movie_detail_page_hides_blacklist_for_an_embedded_subtitle(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_movie_detail_with_embedded_subtitle_handler)

    with TestClient(app) as client:
        response = client.get("/media/movies/1")

    assert response.status_code == 200
    assert "/media/subtitles/9/sync-timing" in response.text
    assert "/media/subtitles/9/blacklist" not in response.text


def test_movie_detail_page_redirects_when_missing(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_missing_movie_handler)

    with TestClient(app) as client:
        response = client.get("/media/movies/1")

    assert response.status_code == 200
    assert response.request.url.path == "/media/movies"
