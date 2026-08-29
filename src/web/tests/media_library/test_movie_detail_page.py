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
    assert "/media/subtitles/9/sync-timing" in response.text
    assert "/media/subtitles/9/translate" in response.text
    assert "/media/subtitles/9/blacklist" in response.text
    assert 'class="lang-pill lang-pill--external"' in response.text
    # The external pill is its own actions-menu trigger (Sync timing, Translate from
    # this, Blacklist), same subtitle-pill-menu.js mechanism as the missing-language
    # pill — the file name is a second way to reach the same actions, in the dialog.
    pill_start = response.text.index('class="lang-pill lang-pill--external"')
    pill_end = response.text.index("</li>", pill_start)
    pill_li = response.text[pill_start:pill_end]
    assert "data-subtitle-file-modal-open" not in pill_li
    assert "data-subtitle-menu-toggle" in pill_li
    assert "/media/subtitles/9/sync-timing" in pill_li
    assert "/media/subtitles/9/translate" in pill_li
    assert "/media/subtitles/9/blacklist" in pill_li
    assert 'class="subtitle-file-title-trigger"' in response.text
    assert 'data-subtitle-file-modal-open="subtitle-file-modal-5"' in response.text


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
    assert "/media/subtitles/9/sync-timing" not in response.text
    assert "/media/subtitles/9/blacklist" not in response.text
    assert 'class="lang-pill lang-pill--embedded"' in response.text


def _movie_detail_with_many_embedded_subtitles_handler(request: httpx.Request) -> httpx.Response:
    response = _movie_detail_handler(request)
    body = response.json()
    body["files"][0]["subtitles"] = [
        {"id": 9, "language": "en", "origin": "embedded"},
        {"id": 10, "language": "ja", "origin": "embedded"},
        {"id": 11, "language": "fr", "origin": "embedded"},
    ]
    return httpx.Response(200, json=body)


def test_movie_detail_page_collapses_embedded_subtitles_into_one_dialog(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_movie_detail_with_many_embedded_subtitles_handler)

    with TestClient(app) as client:
        response = client.get("/media/movies/1")

    assert response.status_code == 200
    # No individual pill for any of the three embedded subtitles — just the collapsed
    # trigger pill (1) plus one row per subtitle inside the dialog (3).
    assert response.text.count('class="lang-pill lang-pill--embedded"') == 4
    assert 'data-subtitle-file-modal-open="subtitle-file-modal-5"' in response.text
    assert 'id="subtitle-file-modal-5"' in response.text
    for subtitle_id in (9, 10, 11):
        assert f"/media/subtitles/{subtitle_id}/sync-timing" not in response.text
        assert f"/media/subtitles/{subtitle_id}/translate" in response.text


def _movie_detail_with_external_and_embedded_subtitles_handler(
    request: httpx.Request,
) -> httpx.Response:
    response = _movie_detail_handler(request)
    body = response.json()
    body["files"][0]["subtitles"] = [
        {"id": 9, "language": "en", "origin": "external"},
        {"id": 10, "language": "ja", "origin": "embedded"},
        {"id": 11, "language": "fr", "origin": "embedded"},
    ]
    return httpx.Response(200, json=body)


def test_movie_detail_page_lists_external_subtitles_in_the_same_dialog(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_movie_detail_with_external_and_embedded_subtitles_handler)

    with TestClient(app) as client:
        response = client.get("/media/movies/1")

    assert response.status_code == 200
    # The external pill opens its own quick actions menu (not the dialog); the embedded
    # pill and the file name are what open the shared per-file dialog instead.
    pill_start = response.text.index('class="lang-pill lang-pill--external"')
    pill_end = response.text.index("</li>", pill_start)
    external_pill_li = response.text[pill_start:pill_end]
    assert "data-subtitle-file-modal-open" not in external_pill_li
    assert "data-subtitle-menu-toggle" in external_pill_li
    assert 'data-subtitle-file-modal-open="subtitle-file-modal-5"' in response.text
    embedded_pill_start = response.text.index('class="lang-pill lang-pill--embedded"')
    embedded_pill_end = response.text.index("</li>", embedded_pill_start)
    assert "data-subtitle-menu-toggle" not in response.text[embedded_pill_start:embedded_pill_end]
    dialog_start = response.text.index('id="subtitle-file-modal-5"')
    dialog = response.text[dialog_start:]
    assert "/media/subtitles/9/blacklist" in dialog
    assert "/media/subtitles/10/sync-timing" not in dialog
    assert "/media/subtitles/11/sync-timing" not in dialog
    assert "/media/subtitles/10/blacklist" not in dialog
    assert "/media/subtitles/11/blacklist" not in dialog


def test_movie_detail_page_shows_the_file_name_in_the_subtitles_dialog(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_movie_detail_with_embedded_subtitle_handler)

    with TestClient(app) as client:
        response = client.get("/media/movies/1")

    assert response.status_code == 200
    assert "<p>Foo.mkv</p>" in response.text


def _movie_detail_with_acquired_subtitle_handler(request: httpx.Request) -> httpx.Response:
    response = _movie_detail_handler(request)
    body = response.json()
    body["files"][0]["subtitles"] = [
        {
            "id": 9,
            "language": "en",
            "origin": "external",
            "size_bytes": 2048,
            "provider": "opensubtitles",
            "release_name": "Foo.2024.1080p.WEB-DL.DDP5.1.H.264-GROUP",
            "score": 0.94,
            "resolution_matched": True,
            "source_matched": True,
            "codec_matched": False,
            "release_group_matched": None,
            "edition_matched": True,
        }
    ]
    return httpx.Response(200, json=body)


def test_movie_detail_page_renders_provider_release_match_score_and_size(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_movie_detail_with_acquired_subtitle_handler)

    with TestClient(app) as client:
        response = client.get("/media/movies/1")

    assert response.status_code == 200
    assert "opensubtitles" in response.text
    assert "Foo.2024.1080p.WEB-DL.DDP5.1.H.264-GROUP" in response.text
    assert "94%" in response.text
    assert "2.0 kB" in response.text
    assert 'class="subtitle-match-badge subtitle-match-badge--yes"' in response.text
    assert 'class="subtitle-match-badge subtitle-match-badge--no"' in response.text
    assert 'class="subtitle-match-badge subtitle-match-badge--na"' in response.text


def test_movie_detail_page_hides_provider_columns_without_acquisition_data(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_movie_detail_handler)

    with TestClient(app) as client:
        response = client.get("/media/movies/1")

    assert response.status_code == 200
    dialog_start = response.text.index('id="subtitle-file-modal-5"')
    dialog = response.text[dialog_start:]
    assert "subtitle-match-badge" not in dialog
    assert "0 Bytes" in dialog


def _movie_detail_with_missing_language_handler(request: httpx.Request) -> httpx.Response:
    response = _movie_detail_handler(request)
    body = response.json()
    body["files"][0]["missing_languages"] = ["fr"]
    return httpx.Response(200, json=body)


def test_movie_detail_page_renders_a_missing_language_as_a_gray_pill(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_movie_detail_with_missing_language_handler)

    with TestClient(app) as client:
        response = client.get("/media/movies/1")

    assert response.status_code == 200
    assert 'class="lang-pill lang-pill--missing"' in response.text
    assert "fr" in response.text
    assert "/media/files/5/translate" in response.text


def _movie_detail_with_no_subtitles_handler(request: httpx.Request) -> httpx.Response:
    response = _movie_detail_handler(request)
    body = response.json()
    body["files"][0]["subtitles"] = []
    return httpx.Response(200, json=body)


def test_movie_detail_page_file_name_is_not_clickable_without_subtitles(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_movie_detail_with_no_subtitles_handler)

    with TestClient(app) as client:
        response = client.get("/media/movies/1")

    assert response.status_code == 200
    # No subtitle at all means no per-file dialog is rendered, so the file name stays
    # plain text instead of a dialog trigger.
    assert 'class="subtitle-file-title-trigger"' not in response.text
    assert "data-subtitle-file-modal-open" not in response.text


def test_movie_detail_page_fetches_an_uncached_poster_on_demand(stub_backend_client):
    """`poster_cached` absent from the backend response (falsy) triggers the on-demand
    fallback (ROADMAP.md 0.20.0), same as a list page."""

    def _handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/media/movies/1/poster-cache":
            return httpx.Response(200, json={"cached": True})
        return _movie_detail_handler(request)

    app = create_app()
    stub_backend_client(app, handler=_handler)

    with TestClient(app) as client:
        response = client.get("/media/movies/1")

    assert response.status_code == 200
    assert "/posters/movie_1.jpg" in response.text
    assert "https://example.test/foo.jpg" not in response.text


def test_movie_detail_page_redirects_when_missing(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_missing_movie_handler)

    with TestClient(app) as client:
        response = client.get("/media/movies/1")

    assert response.status_code == 200
    assert response.request.url.path == "/media/movies"
