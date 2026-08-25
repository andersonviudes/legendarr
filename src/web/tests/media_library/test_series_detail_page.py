import httpx
from fastapi.testclient import TestClient
from legendarr_web.app import create_app


def _series_detail_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "id": 1,
            "title": "Bar",
            "monitored": True,
            "status": "continuing",
            "quality_profile_name": "Any",
            "overview": None,
            "poster_url": "https://example.test/bar.jpg",
            "year": 2024,
            "imdb_rating": None,
            "episode_count": 2,
            "episode_file_count": 1,
            "remote_path": "/tv/Bar",
            "language_profile_name": "Default",
            "target_languages": ["pt-BR"],
            "missing_subtitles_count": 0,
            "episodes": [
                {
                    "season_number": 1,
                    "episode_number": 1,
                    "title": "Pilot",
                    "media_file": {
                        "id": 5,
                        "relative_path": "Season 01/Bar.S01E01.mkv",
                        "size_bytes": 100,
                        "subtitles": [{"id": 12, "language": "pt-BR", "origin": "external"}],
                    },
                },
                {
                    "season_number": 1,
                    "episode_number": 2,
                    "title": "TBA",
                    "media_file": None,
                },
            ],
        },
    )


def _missing_series_handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/media/series/1":
        return httpx.Response(404, json={"detail": "Series not found"})
    return httpx.Response(200, json=[])


def _unavailable_series_handler(request: httpx.Request) -> httpx.Response:
    response = _series_detail_handler(request)
    body = response.json()
    body["episodes"] = []
    body["episodes_unavailable"] = True
    return httpx.Response(200, json=body)


def test_series_detail_page_renders_episodes_grouped_by_season(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_series_detail_handler)

    with TestClient(app) as client:
        response = client.get("/media/series/1")

    assert response.status_code == 200
    assert "Bar" in response.text
    assert "Season 1" in response.text
    assert "Pilot" in response.text
    assert "pt-BR" in response.text
    assert response.text.count("/media/files/5/translate") == 1
    assert "/media/subtitles/12/sync-timing" in response.text
    assert "/media/subtitles/12/translate" in response.text
    assert "TBA" in response.text
    assert 'class="lang-pill lang-pill--external"' in response.text


def _series_detail_with_missing_language_handler(request: httpx.Request) -> httpx.Response:
    response = _series_detail_handler(request)
    body = response.json()
    body["episodes"][0]["media_file"]["missing_languages"] = ["fr"]
    return httpx.Response(200, json=body)


def test_series_detail_page_renders_a_missing_language_as_a_gray_pill(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_series_detail_with_missing_language_handler)

    with TestClient(app) as client:
        response = client.get("/media/series/1")

    assert response.status_code == 200
    assert 'class="lang-pill lang-pill--missing"' in response.text
    assert "fr" in response.text


def test_series_detail_page_shows_unavailable_message_when_sonarr_unreachable(
    stub_backend_client,
):
    app = create_app()
    stub_backend_client(app, handler=_unavailable_series_handler)

    with TestClient(app) as client:
        response = client.get("/media/series/1")

    assert response.status_code == 200
    assert "reach Sonarr" in response.text
    assert "No episodes found for this series yet." not in response.text


def test_series_detail_page_redirects_when_missing(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_missing_series_handler)

    with TestClient(app) as client:
        response = client.get("/media/series/1")

    assert response.status_code == 200
    assert response.request.url.path == "/media/series"
