import httpx
from fastapi.testclient import TestClient
from legendarr_web.app import create_app


def _blacklist_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "success": True,
            "message": "Blacklisted en subtitle",
            "media_file_id": 5,
            "subtitles": [],
        },
    )


def _blacklist_failure_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(404, json={"detail": "Subtitle not found"})


def test_blacklist_subtitle_swaps_subtitle_cell(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_blacklist_handler)

    with TestClient(app) as client:
        response = client.post("/media/subtitles/9/blacklist")

    assert response.status_code == 200
    assert 'data-toast-type="success"' in response.text
    assert 'id="subtitles-cell-5"' in response.text
    assert 'hx-swap-oob="true"' in response.text


def test_blacklist_subtitle_shows_error_on_failure(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_blacklist_failure_handler)

    with TestClient(app) as client:
        response = client.post("/media/subtitles/9/blacklist")

    assert response.status_code == 200
    assert 'data-toast-type="error"' in response.text
    assert "Couldn&#39;t blacklist the subtitle." in response.text
    assert 'hx-swap-oob="true"' not in response.text
