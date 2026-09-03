from urllib.parse import parse_qs

import httpx
from fastapi.testclient import TestClient
from legendarr_web.app import create_app


def _subtitles_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200,
        json=[
            {"id": 9, "language": "en", "origin": "external"},
            {"id": 10, "language": "fr", "origin": "embedded"},
        ],
    )


def _single_subtitle_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json=[{"id": 9, "language": "en", "origin": "external"}])


def _sync_failure_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(404, json={"detail": "Subtitle not found"})


def test_subtitle_sync_panel_excludes_the_subtitle_itself(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_subtitles_handler)

    with TestClient(app) as client:
        response = client.get("/media/subtitles/9/sync-timing?media_file_id=5")

    assert response.status_code == 200
    assert "Sync using audio" in response.text
    assert 'value="10"' in response.text
    assert 'value="9"' not in response.text


def test_subtitle_sync_panel_shows_empty_state_without_other_subtitles(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_single_subtitle_handler)

    with TestClient(app) as client:
        response = client.get("/media/subtitles/9/sync-timing?media_file_id=5")

    assert response.status_code == 200
    assert "No other subtitle on this file to sync from." in response.text
    assert 'name="reference_subtitle_id"' not in response.text


def test_trigger_subtitle_timing_sync_forwards_reference_subtitle_id(stub_backend_client):
    app = create_app()
    captured = {}

    def _handler(request: httpx.Request) -> httpx.Response:
        captured["form"] = parse_qs(request.read().decode())
        return httpx.Response(200, json={"status": "enqueued"})

    stub_backend_client(app, handler=_handler)

    with TestClient(app) as client:
        response = client.post(
            "/media/subtitles/9/sync-timing", data={"reference_subtitle_id": "10"}
        )

    assert response.status_code == 200
    assert 'data-toast-type="success"' in response.text
    assert captured["form"] == {"reference_subtitle_id": ["10"]}


def test_trigger_subtitle_timing_sync_shows_error_on_failure(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_sync_failure_handler)

    with TestClient(app) as client:
        response = client.post("/media/subtitles/9/sync-timing")

    assert response.status_code == 200
    assert 'data-toast-type="error"' in response.text
