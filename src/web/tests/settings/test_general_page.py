import json

import httpx
from fastapi.testclient import TestClient
from legendarr_web.app import create_app


def _general_settings_handler(locale: str):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/settings/general" and request.method == "PUT":
            body = json.loads(request.content)
            return httpx.Response(200, json=body)
        if request.url.path == "/settings/general":
            return httpx.Response(200, json={"ui_locale": locale})
        return httpx.Response(200, json=[])

    return handler


def test_general_page_renders_the_saved_locale(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_general_settings_handler("en"), stub_general_settings=False)

    with TestClient(app) as client:
        response = client.get("/settings/general/")

    assert response.status_code == 200
    assert 'value="en" selected' in response.text


def test_general_page_renders_chrome_in_the_saved_locale(stub_backend_client):
    app = create_app()
    stub_backend_client(
        app, handler=_general_settings_handler("pt-BR"), stub_general_settings=False
    )

    with TestClient(app) as client:
        response = client.get("/settings/general/")

    assert response.status_code == 200
    assert 'value="pt-BR" selected' in response.text
    # The shared chrome (sidebar) is translated too, not just the settings form itself.
    assert "Configurações" in response.text


def test_save_general_settings_puts_to_backend_and_redirects_with_toast(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_general_settings_handler("en"), stub_general_settings=False)

    with TestClient(app) as client:
        response = client.post(
            "/settings/general/", data={"ui_locale": "es"}, follow_redirects=False
        )

    assert response.status_code == 303
    location = response.headers["location"]
    assert location.startswith("/settings/general/?")
    assert "General+settings+saved." in location


def test_save_general_settings_renders_error_on_backend_rejection(stub_backend_client):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/settings/general" and request.method == "PUT":
            return httpx.Response(422, json={"detail": "Unsupported locale"})
        if request.url.path == "/settings/general":
            return httpx.Response(200, json={"ui_locale": "en"})
        return httpx.Response(200, json=[])

    app = create_app()
    stub_backend_client(app, handler=handler, stub_general_settings=False)

    with TestClient(app) as client:
        response = client.post(
            "/settings/general/", data={"ui_locale": "fr"}, follow_redirects=False
        )

    assert response.status_code == 422
    assert "Unsupported locale" in response.text
