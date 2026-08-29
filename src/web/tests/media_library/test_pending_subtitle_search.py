import httpx
from fastapi.testclient import TestClient
from legendarr_web.app import create_app


def _target_languages_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json=["pt-BR", "fr"])


def _no_target_languages_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json=[])


def _candidates_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200,
        json=[
            {
                "provider": "opensubtitles",
                "release_name": "Ahsoka.S01E04.1080p.WEB-DL",
                "download_id": "abc123",
                "language": "en",
                "page_link": "https://example.test/sub/abc123",
                "score": 0.87,
            }
        ],
    )


def _empty_candidates_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json=[])


def _download_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"success": True, "message": "Subtitle held for later."})


def _download_failure_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(404, json={"detail": "Series not found"})


def test_pending_subtitle_search_panel_has_no_language_picker(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_target_languages_handler)

    with TestClient(app) as client:
        response = client.get("/media/series/1/episodes/1/4/subtitle-search")

    assert response.status_code == 200
    assert "Search providers" in response.text
    assert "<select" not in response.text
    assert (
        "/media/series/1/episodes/1/4/subtitle-search/results?languages=pt-BR&languages=fr"
        in response.text
    )


def test_pending_subtitle_search_panel_shows_empty_state_without_target_languages(
    stub_backend_client,
):
    app = create_app()
    stub_backend_client(app, handler=_no_target_languages_handler)

    with TestClient(app) as client:
        response = client.get("/media/series/1/episodes/1/4/subtitle-search")

    assert response.status_code == 200
    assert "No target languages configured" in response.text
    assert "/media/series/1/episodes/1/4/subtitle-search/results" not in response.text


def test_pending_subtitle_search_results_renders_candidates(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_candidates_handler)

    with TestClient(app) as client:
        response = client.get(
            "/media/series/1/episodes/1/4/subtitle-search/results", params={"languages": ["en"]}
        )

    assert response.status_code == 200
    assert "Ahsoka.S01E04.1080p.WEB-DL" in response.text
    assert "opensubtitles" in response.text
    assert "87%" in response.text
    assert "/media/series/1/episodes/1/4/subtitle-candidates/download" in response.text


def test_pending_subtitle_search_results_empty_state(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_empty_candidates_handler)

    with TestClient(app) as client:
        response = client.get(
            "/media/series/1/episodes/1/4/subtitle-search/results", params={"languages": ["en"]}
        )

    assert response.status_code == 200
    assert "No subtitles found" in response.text


def test_download_pending_subtitle_candidate_shows_success_message(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_download_handler)

    with TestClient(app) as client:
        response = client.post(
            "/media/series/1/episodes/1/4/subtitle-candidates/download",
            data={
                "provider": "opensubtitles",
                "release_name": "Ahsoka.S01E04.1080p.WEB-DL",
                "download_id": "abc123",
                "language": "en",
                "target_language": "en",
                "page_link": "",
            },
        )

    assert response.status_code == 200
    assert 'data-toast-type="success"' in response.text
    assert "Subtitle held for later." in response.text
    # No file row exists yet — nothing to OOB-swap.
    assert "hx-swap-oob" not in response.text


def test_download_pending_subtitle_candidate_shows_error_on_failure(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_download_failure_handler)

    with TestClient(app) as client:
        response = client.post(
            "/media/series/1/episodes/1/4/subtitle-candidates/download",
            data={
                "provider": "opensubtitles",
                "release_name": "Ahsoka.S01E04.1080p.WEB-DL",
                "download_id": "abc123",
                "language": "en",
                "target_language": "en",
                "page_link": "",
            },
        )

    assert response.status_code == 200
    assert 'data-toast-type="error"' in response.text
    assert "Couldn&#39;t download the subtitle." in response.text
