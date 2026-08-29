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


def test_subtitle_search_panel_has_no_language_picker(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_target_languages_handler)

    with TestClient(app) as client:
        response = client.get("/media/files/5/subtitle-search")

    assert response.status_code == 200
    assert "Search providers" in response.text
    assert "<select" not in response.text
    assert "/media/files/5/subtitle-search/results?languages=pt-BR&languages=fr" in response.text


def test_subtitle_search_panel_shows_empty_state_without_target_languages(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_no_target_languages_handler)

    with TestClient(app) as client:
        response = client.get("/media/files/5/subtitle-search")

    assert response.status_code == 200
    assert "No target languages configured" in response.text
    assert "/media/files/5/subtitle-search/results" not in response.text


def test_subtitle_search_panel_preselects_the_given_language(stub_backend_client):
    """A subtitle pill's own "Search" action passes its language, matched
    case-insensitively against SUPPORTED_LANGUAGES since the pill's own casing (e.g.
    "pt-br") isn't guaranteed to match the canonical form ("pt-BR") — searches just
    that one upgrade instead of every target language."""
    app = create_app()
    stub_backend_client(app)

    with TestClient(app) as client:
        response = client.get("/media/files/5/subtitle-search", params={"language": "pt-br"})

    assert response.status_code == 200
    assert "pt-BR" in response.text
    assert "/media/files/5/subtitle-search/results?languages=pt-BR" in response.text


def test_subtitle_search_panel_falls_back_to_target_languages_for_an_unrecognized_language(
    stub_backend_client,
):
    app = create_app()
    stub_backend_client(app, handler=_target_languages_handler)

    with TestClient(app) as client:
        response = client.get("/media/files/5/subtitle-search", params={"language": "xx-not-real"})

    assert response.status_code == 200
    assert "pt-BR" in response.text
    assert "fr" in response.text


def test_subtitle_search_results_renders_candidates(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_candidates_handler)

    with TestClient(app) as client:
        response = client.get(
            "/media/files/5/subtitle-search/results", params={"languages": ["en"]}
        )

    assert response.status_code == 200
    assert "Foo.2024.1080p.WEB-DL" in response.text
    assert "opensubtitles" in response.text
    assert "87%" in response.text
    assert "https://example.test/sub/abc123" in response.text
    # The download button must persist the searched language, not the provider-reported one.
    assert '"target_language": "en"' in response.text


def test_subtitle_search_results_merges_multiple_languages(stub_backend_client):
    calls: list[str] = []

    def _handler(request: httpx.Request) -> httpx.Response:
        language = request.url.params["language"]
        calls.append(language)
        return httpx.Response(
            200,
            json=[
                {
                    "provider": "opensubtitles",
                    "release_name": f"Foo.{language}",
                    "download_id": language,
                    "language": language,
                    "page_link": None,
                    "score": 0.5,
                }
            ],
        )

    app = create_app()
    stub_backend_client(app, handler=_handler)

    with TestClient(app) as client:
        response = client.get(
            "/media/files/5/subtitle-search/results",
            params={"languages": ["pt-BR", "fr"]},
        )

    assert response.status_code == 200
    assert calls == ["pt-BR", "fr"]
    assert "Foo.pt-BR" in response.text
    assert "Foo.fr" in response.text
    assert '"target_language": "pt-BR"' in response.text
    assert '"target_language": "fr"' in response.text


def test_subtitle_search_results_empty_state(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_empty_candidates_handler)

    with TestClient(app) as client:
        response = client.get(
            "/media/files/5/subtitle-search/results", params={"languages": ["en"]}
        )

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
