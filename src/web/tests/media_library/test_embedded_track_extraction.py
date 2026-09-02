import httpx
from fastapi.testclient import TestClient
from legendarr_web.app import create_app


def _extract_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "success": True,
            "message": "Track extracted.",
            "subtitles": [],
            "embedded_tracks": [],
            "missing_languages": [],
            "has_source_subtitle": False,
        },
    )


def _extract_failure_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(404, json={"detail": "Embedded track not found"})


def test_extract_embedded_track_swaps_subtitle_cell(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_extract_handler)

    with TestClient(app) as client:
        response = client.post("/media/files/5/embedded-tracks/2/extract")

    assert response.status_code == 200
    assert 'data-toast-type="success"' in response.text
    assert 'id="subtitles-cell-5"' in response.text
    assert 'hx-swap-oob="true"' in response.text


def test_extract_embedded_track_shows_error_on_failure(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_extract_failure_handler)

    with TestClient(app) as client:
        response = client.post("/media/files/5/embedded-tracks/2/extract")

    assert response.status_code == 200
    assert 'data-toast-type="error"' in response.text
    assert "Couldn&#39;t extract this track." in response.text
    assert 'hx-swap-oob="true"' not in response.text
