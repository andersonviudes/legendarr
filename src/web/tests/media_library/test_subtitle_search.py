import httpx
from fastapi.testclient import TestClient
from legendarr_web.app import create_app


def _candidates_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200,
        json=[
            {
                "provider": "opensubtitles",
                "release_name": "Foo.2024.1080p.WEB-DL",
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
    return httpx.Response(
        200,
        json={
            "success": True,
            "message": "Subtitle downloaded.",
            "subtitles": [{"id": 9, "language": "en", "origin": "external"}],
        },
    )


def _download_failure_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(404, json={"detail": "Media file not found"})


def test_subtitle_search_panel_renders_language_select(stub_backend_client):
    app = create_app()
    stub_backend_client(app)

    with TestClient(app) as client:
        response = client.get("/media/files/5/subtitle-search")

    assert response.status_code == 200
    assert "Search providers" in response.text
    assert 'name="language"' in response.text
    assert "/media/files/5/subtitle-search/results" in response.text


def test_subtitle_search_panel_preselects_the_given_language(stub_backend_client):
    """A subtitle pill's own "Search" action passes its language, matched
    case-insensitively against SUPPORTED_LANGUAGES since the pill's own casing (e.g.
    "pt-br") isn't guaranteed to match the option's ("pt-BR")."""
    app = create_app()
    stub_backend_client(app)

    with TestClient(app) as client:
        response = client.get("/media/files/5/subtitle-search", params={"language": "pt-br"})

    assert response.status_code == 200
    assert '<option value="pt-BR" selected>' in response.text


def test_subtitle_search_panel_ignores_an_unrecognized_language(stub_backend_client):
    app = create_app()
    stub_backend_client(app)

    with TestClient(app) as client:
        response = client.get("/media/files/5/subtitle-search", params={"language": "xx-not-real"})

    assert response.status_code == 200
    assert "selected" not in response.text


def test_subtitle_search_results_renders_candidates(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_candidates_handler)

    with TestClient(app) as client:
        response = client.get("/media/files/5/subtitle-search/results", params={"language": "en"})

    assert response.status_code == 200
    assert "Foo.2024.1080p.WEB-DL" in response.text
    assert "opensubtitles" in response.text
    assert "87%" in response.text
    assert "https://example.test/sub/abc123" in response.text
    # The download button must persist the searched language, not the provider-reported one.
    assert '"target_language": "en"' in response.text


def test_subtitle_search_results_empty_state(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_empty_candidates_handler)

    with TestClient(app) as client:
        response = client.get("/media/files/5/subtitle-search/results", params={"language": "en"})

    assert response.status_code == 200
    assert "No subtitles found" in response.text


def test_download_subtitle_candidate_swaps_subtitle_cell(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_download_handler)

    with TestClient(app) as client:
        response = client.post(
            "/media/files/5/subtitle-candidates/download",
            data={
                "provider": "opensubtitles",
                "release_name": "Foo.2024.1080p.WEB-DL",
                "download_id": "abc123",
                "language": "en",
                "target_language": "en",
                "page_link": "",
            },
        )

    assert response.status_code == 200
    assert 'id="subtitles-cell-5"' in response.text
    assert 'hx-swap-oob="true"' in response.text
    assert 'data-toast-type="success"' in response.text
    assert "Subtitle downloaded." in response.text
    assert "subtitle-acquire-result--success" in response.text


def test_download_subtitle_candidate_shows_error_on_failure(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_download_failure_handler)

    with TestClient(app) as client:
        response = client.post(
            "/media/files/5/subtitle-candidates/download",
            data={
                "provider": "opensubtitles",
                "release_name": "Foo.2024.1080p.WEB-DL",
                "download_id": "abc123",
                "language": "en",
                "target_language": "en",
                "page_link": "",
            },
        )

    assert response.status_code == 200
    assert 'data-toast-type="error"' in response.text
    assert "hx-swap-oob" not in response.text
    assert "Couldn&#39;t download the subtitle." in response.text
    assert "subtitle-acquire-result--error" in response.text
