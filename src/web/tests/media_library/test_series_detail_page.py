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
                    "pending_languages": [],
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
    assert "/media/subtitles/12/sync-timing" in response.text
    assert "/media/subtitles/12/translate" in response.text
    assert "TBA" in response.text
    assert 'class="lang-pill lang-pill--external"' in response.text
    # Only the episode with a file gets a dialog trigger on its title — the fileless
    # "TBA" episode has nothing to open. The external pill opens its own quick actions
    # menu instead of the dialog.
    assert response.text.count('class="subtitle-file-title-trigger"') == 1
    assert 'data-subtitle-file-modal-open="subtitle-file-modal-5"' in response.text
    pill_start = response.text.index('class="lang-pill lang-pill--external"')
    pill_end = response.text.index("</li>", pill_start)
    pill_li = response.text[pill_start:pill_end]
    assert "data-subtitle-file-modal-open" not in pill_li
    assert "data-subtitle-menu-toggle" in pill_li
    assert "/media/subtitles/12/sync-timing" in pill_li
    assert "/media/subtitles/12/translate" in pill_li
    assert "/media/subtitles/12/remove-style-tags" in pill_li
    assert "/media/files/5/subtitle-search?language=pt-BR" in pill_li
    # The Actions column's own "Search" button opens the same manual-search panel as
    # the pill's "Search" action, but with no language pre-selected — it's file-level,
    # not tied to one already-downloaded subtitle. Episode 2 ("TBA", no media file)
    # renders first — episodes are sorted by episode_number descending — so its
    # pending-episode Actions div comes before episode 1's ("Pilot") file-based one.
    pending_actions_start = response.text.index('class="file-row-actions"')
    pending_actions_end = response.text.index("</div>", pending_actions_start)
    pending_actions_html = response.text[pending_actions_start:pending_actions_end]
    assert "/media/series/1/episodes/1/2/subtitle-search" in pending_actions_html
    assert "/media/series/1/episodes/1/2/subtitle-upload" in pending_actions_html

    actions_start = response.text.index('class="file-row-actions"', pending_actions_end)
    actions_end = response.text.index("</div>", actions_start)
    actions_html = response.text[actions_start:actions_end]
    assert 'hx-get="/media/files/5/subtitle-search"' in actions_html
    assert "/media/files/5/subtitle-upload" in actions_html


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


def _series_detail_with_pending_subtitle_handler(request: httpx.Request) -> httpx.Response:
    response = _series_detail_handler(request)
    body = response.json()
    body["episodes"][1]["pending_languages"] = ["pt-BR"]
    return httpx.Response(200, json=body)


def test_series_detail_page_renders_a_pending_subtitle_as_a_distinct_pill(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_series_detail_with_pending_subtitle_handler)

    with TestClient(app) as client:
        response = client.get("/media/series/1")

    assert response.status_code == 200
    assert 'class="lang-pill lang-pill--pending"' in response.text


def _series_detail_with_many_embedded_subtitles_handler(request: httpx.Request) -> httpx.Response:
    response = _series_detail_handler(request)
    body = response.json()
    body["episodes"][0]["media_file"]["subtitles"] = [
        {"id": 21, "language": "en", "origin": "embedded"},
        {"id": 22, "language": "ja", "origin": "embedded"},
    ]
    return httpx.Response(200, json=body)


def test_series_detail_page_collapses_embedded_subtitles_into_one_dialog(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_series_detail_with_many_embedded_subtitles_handler)

    with TestClient(app) as client:
        response = client.get("/media/series/1")

    assert response.status_code == 200
    # Trigger pill (1) plus one row per embedded subtitle inside the dialog (2).
    assert response.text.count('class="lang-pill lang-pill--embedded"') == 3
    assert 'id="subtitle-file-modal-5"' in response.text
    assert "/media/subtitles/21/sync-timing" not in response.text
    assert "/media/subtitles/22/sync-timing" not in response.text
    assert "<p>Season 01/Bar.S01E01.mkv</p>" in response.text


def _series_detail_with_acquired_subtitle_handler(request: httpx.Request) -> httpx.Response:
    response = _series_detail_handler(request)
    body = response.json()
    body["episodes"][0]["media_file"]["subtitles"] = [
        {
            "id": 12,
            "language": "pt-BR",
            "origin": "external",
            "size_bytes": 2048,
            "provider": "legendas_net",
            "release_name": "Bar.S01E01.1080p.WEB-DL-GROUP",
            "score": 0.87,
            "resolution_matched": True,
            "source_matched": False,
            "codec_matched": None,
            "release_group_matched": True,
            "edition_matched": None,
        }
    ]
    return httpx.Response(200, json=body)


def test_series_detail_page_renders_provider_release_match_score_and_size(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_series_detail_with_acquired_subtitle_handler)

    with TestClient(app) as client:
        response = client.get("/media/series/1")

    assert response.status_code == 200
    assert "legendas_net" in response.text
    assert "Bar.S01E01.1080p.WEB-DL-GROUP" in response.text
    assert "87%" in response.text
    assert "2.0 kB" in response.text
    assert 'class="subtitle-match-bar"' in response.text
    assert '<span class="subtitle-match-bar-label">87%</span>' in response.text
    assert "Resolution: Matched" in response.text
    assert "Source: Not matched" in response.text
    assert "Codec: Not compared" in response.text


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
