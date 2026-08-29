import httpx
from fastapi.testclient import TestClient
from legendarr_web.app import create_app


def _upload_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"success": True, "message": "Subtitle held for later."})


def _upload_failure_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(400, json={"detail": "Unsupported file type"})


def test_pending_subtitle_upload_panel_renders_language_select(stub_backend_client):
    app = create_app()
    stub_backend_client(app)

    with TestClient(app) as client:
        response = client.get("/media/series/1/episodes/1/4/subtitle-upload")

    assert response.status_code == 200
    assert "Upload a subtitle file" in response.text
    assert 'name="language"' in response.text
    assert 'name="file"' in response.text


def test_upload_pending_subtitle_shows_success_message(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_upload_handler)

    with TestClient(app) as client:
        response = client.post(
            "/media/series/1/episodes/1/4/subtitle-upload",
            data={"language": "en"},
            files={
                "file": (
                    "Ahsoka.en.srt",
                    b"1\n00:00:00,000 --> 00:00:01,000\nHi\n",
                    "text/plain",
                )
            },
        )

    assert response.status_code == 200
    assert 'data-toast-type="success"' in response.text
    assert "Subtitle held for later." in response.text
    assert "hx-swap-oob" not in response.text


def test_upload_pending_subtitle_shows_error_on_failure(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_upload_failure_handler)

    with TestClient(app) as client:
        response = client.post(
            "/media/series/1/episodes/1/4/subtitle-upload",
            data={"language": "en"},
            files={"file": ("Ahsoka.txt", b"not a subtitle", "text/plain")},
        )

    assert response.status_code == 200
    assert 'data-toast-type="error"' in response.text
    assert "Couldn&#39;t upload the subtitle." in response.text
