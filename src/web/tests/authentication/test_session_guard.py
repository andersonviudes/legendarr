import httpx
from fastapi.testclient import TestClient
from legendarr_web.app import create_app


def _unauthenticated_handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/auth/sessions/validate":
        return httpx.Response(
            200, json={"authenticated": False, "auth_enabled": True, "session": None}
        )
    return httpx.Response(200, json=[])


def _authenticated_handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/auth/sessions/validate":
        return httpx.Response(
            200,
            json={
                "authenticated": True,
                "auth_enabled": True,
                "session": {
                    "id": 1,
                    "created_at": "2026-08-01T00:00:00",
                    "last_seen_at": "2026-08-26T00:00:00",
                    "expires_at": "2026-09-25T00:00:00",
                    "ip_address": "127.0.0.1",
                    "user_agent": "pytest",
                },
            },
        )
    return httpx.Response(200, json=[])


def test_plain_navigation_redirects_to_login_when_unauthenticated(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_unauthenticated_handler, stub_auth_validate=False)

    with TestClient(app) as client:
        response = client.get("/", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/login?next=/"


def test_htmx_request_gets_an_hx_redirect_header_instead_of_a_303(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_unauthenticated_handler, stub_auth_validate=False)

    with TestClient(app) as client:
        response = client.get(
            "/system/tasks/running", headers={"HX-Request": "true"}, follow_redirects=False
        )

    assert response.status_code == 200
    assert response.headers["hx-redirect"] == "/login?next=/system/tasks/running"


def test_login_page_itself_is_never_gated(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_unauthenticated_handler, stub_auth_validate=False)

    with TestClient(app) as client:
        response = client.get("/login")

    assert response.status_code == 200


def test_authenticated_session_passes_through(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_authenticated_handler, stub_auth_validate=False)

    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200


def test_auth_disabled_never_redirects(stub_backend_client):
    app = create_app()
    stub_backend_client(app)  # default handler answers "auth disabled"

    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
