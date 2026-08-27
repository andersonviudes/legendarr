import json

import httpx
from fastapi.testclient import TestClient
from legendarr_web.app import create_app


def _general_settings_handler(locale: str, public_url: str = ""):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/settings/general" and request.method == "PUT":
            body = json.loads(request.content)
            return httpx.Response(200, json=body)
        if request.url.path == "/settings/general":
            return httpx.Response(200, json={"ui_locale": locale})
        if request.url.path == "/settings/webhooks" and request.method == "PUT":
            body = json.loads(request.content)
            return httpx.Response(200, json=body)
        if request.url.path == "/settings/webhooks":
            return httpx.Response(200, json={"public_url": public_url})
        return httpx.Response(200, json=[])

    return handler


def test_general_page_renders_the_saved_locale(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_general_settings_handler("en"), stub_general_settings=False)

    with TestClient(app) as client:
        response = client.get("/settings/general/")

    assert response.status_code == 200
    assert 'value="en" selected' in response.text


def test_general_page_renders_the_saved_legendarr_url(stub_backend_client):
    app = create_app()
    stub_backend_client(
        app,
        handler=_general_settings_handler("en", public_url="https://legendarr.example.com"),
        stub_general_settings=False,
    )

    with TestClient(app) as client:
        response = client.get("/settings/general/")

    assert response.status_code == 200
    assert 'value="https://legendarr.example.com"' in response.text


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
    # The toast reflects the newly-saved locale (es), not the one active when the
    # request started (en) — this is the one page where the two can differ.
    assert "Configuraci%C3%B3n+general+guardada." in location


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


def test_save_general_settings_also_saves_legendarr_url(stub_backend_client):
    app = create_app()
    saved: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "PUT" and request.url.path == "/settings/webhooks":
            saved.update(json.loads(request.content))
            return httpx.Response(200, json=saved)
        return _general_settings_handler("en")(request)

    stub_backend_client(app, handler=handler, stub_general_settings=False)

    with TestClient(app) as client:
        response = client.post(
            "/settings/general/",
            data={"ui_locale": "en", "public_url": "https://legendarr.example.com"},
            follow_redirects=False,
        )

    assert response.status_code == 303
    assert "toast=General+settings+saved." in response.headers["location"]
    assert saved == {"public_url": "https://legendarr.example.com"}
