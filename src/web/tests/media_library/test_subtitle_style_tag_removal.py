import httpx
from fastapi.testclient import TestClient
from legendarr_web.app import create_app


def _cleaned_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"status": "cleaned"})


def _unsupported_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"status": "unsupported"})


def _failure_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(404, json={"detail": "Subtitle not found"})


def test_remove_style_tags_toasts_success(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_cleaned_handler)

    with TestClient(app) as client:
        response = client.post("/media/subtitles/9/remove-style-tags")

    assert response.status_code == 200
    assert 'data-toast-type="success"' in response.text
    assert "Style tags removed." in response.text


def test_remove_style_tags_toasts_a_warning_for_an_unsupported_format(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_unsupported_handler)

    with TestClient(app) as client:
        response = client.post("/media/subtitles/9/remove-style-tags")

    assert response.status_code == 200
    assert 'data-toast-type="error"' in response.text
    assert "This subtitle&#39;s format isn&#39;t supported yet." in response.text


def test_remove_style_tags_shows_error_on_failure(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_failure_handler)

    with TestClient(app) as client:
        response = client.post("/media/subtitles/9/remove-style-tags")

    assert response.status_code == 200
    assert 'data-toast-type="error"' in response.text
    assert "Couldn&#39;t remove style tags." in response.text
