import json

import httpx
from fastapi.testclient import TestClient
from legendarr_web.app import create_app
from legendarr_web.backend_client.client import SESSION_COOKIE_NAME


def _login_handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/auth/login":
        body = json.loads(request.content)
        if body["password"] == "hunter2":
            return httpx.Response(
                200, json={"token": "a-session-token", "expires_at": "2026-09-25T00:00:00"}
            )
        return httpx.Response(401, json={"detail": "Invalid username or password"})
    if request.url.path == "/auth/logout":
        return httpx.Response(204)
    return httpx.Response(200, json=[])


def test_get_login_renders_the_form(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_login_handler)

    with TestClient(app) as client:
        response = client.get("/login")

    assert response.status_code == 200
    assert "Log in" in response.text


def test_post_login_with_valid_credentials_sets_cookie_and_redirects(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_login_handler)

    with TestClient(app) as client:
        response = client.post(
            "/login",
            data={"username": "admin", "password": "hunter2", "next": "/"},
            follow_redirects=False,
        )

    assert response.status_code == 303
    assert response.headers["location"] == "/"
    assert response.cookies[SESSION_COOKIE_NAME] == "a-session-token"


def test_post_login_honors_the_next_parameter(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_login_handler)

    with TestClient(app) as client:
        response = client.post(
            "/login",
            data={"username": "admin", "password": "hunter2", "next": "/settings/"},
            follow_redirects=False,
        )

    assert response.headers["location"] == "/settings/"


def test_post_login_rejects_an_unsafe_next_parameter(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_login_handler)

    with TestClient(app) as client:
        response = client.post(
            "/login",
            data={"username": "admin", "password": "hunter2", "next": "//evil.example.com"},
            follow_redirects=False,
        )

    assert response.headers["location"] == "/"


def test_post_login_with_wrong_password_rerenders_with_error(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_login_handler)

    with TestClient(app) as client:
        response = client.post(
            "/login",
            data={"username": "admin", "password": "wrong", "next": "/"},
            follow_redirects=False,
        )

    assert response.status_code == 401
    assert "Invalid username or password" in response.text
    assert SESSION_COOKIE_NAME not in response.cookies


def test_post_logout_clears_cookie_and_redirects_to_login(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_login_handler)

    with TestClient(app) as client:
        client.cookies.set(SESSION_COOKIE_NAME, "a-session-token")
        response = client.post("/logout", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/login"
    assert response.cookies.get(SESSION_COOKIE_NAME) is None
