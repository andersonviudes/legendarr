import json

import httpx
from fastapi.testclient import TestClient
from legendarr_web.app import create_app

_AUTH_SETTINGS = {"enabled": False, "username": "", "api_key": ""}


def _auth_settings_handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/auth/settings" and request.method == "PUT":
        body = json.loads(request.content)
        return httpx.Response(200, json={**_AUTH_SETTINGS, **body, "api_key": "generated-key"})
    if request.url.path == "/auth/settings":
        return httpx.Response(200, json=_AUTH_SETTINGS)
    return httpx.Response(200, json=[])


def test_authentication_page_renders_defaults(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_auth_settings_handler)

    with TestClient(app) as client:
        response = client.get("/settings/authentication/")

    assert response.status_code == 200
    assert "Require login" in response.text
    assert "Generated automatically" in response.text


def test_save_auth_settings_puts_to_backend_and_redirects_with_toast(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_auth_settings_handler)

    with TestClient(app) as client:
        response = client.post(
            "/settings/authentication/",
            data={"enabled": "true", "username": "admin", "password": "hunter2"},
            follow_redirects=False,
        )

    assert response.status_code == 303
    location = response.headers["location"]
    assert location.startswith("/settings/authentication/?")
    assert "Authentication+settings+saved." in location


def test_save_auth_settings_renders_error_on_backend_rejection(stub_backend_client):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/auth/settings" and request.method == "PUT":
            return httpx.Response(
                400, json={"detail": "Enabling login requires a username and password to be set"}
            )
        if request.url.path == "/auth/settings":
            return httpx.Response(200, json=_AUTH_SETTINGS)
        return httpx.Response(200, json=[])

    app = create_app()
    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.post(
            "/settings/authentication/",
            data={"enabled": "true", "username": "", "password": ""},
            follow_redirects=False,
        )

    assert response.status_code == 400
    assert "Enabling login requires a username and password to be set" in response.text


def test_api_key_field_shows_once_generated(stub_backend_client):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/auth/settings":
            return httpx.Response(
                200, json={"enabled": True, "username": "admin", "api_key": "generated-key"}
            )
        return httpx.Response(200, json=[])

    app = create_app()
    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.get("/settings/authentication/")

    assert "generated-key" in response.text
    assert "/api/docs" in response.text


def test_regenerate_api_key_returns_the_updated_partial(stub_backend_client):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/auth/settings/api-key/regenerate":
            return httpx.Response(
                200, json={"enabled": True, "username": "admin", "api_key": "new-key"}
            )
        return httpx.Response(200, json=[])

    app = create_app()
    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.post("/settings/authentication/api-key/regenerate")

    assert response.status_code == 200
    assert "new-key" in response.text
