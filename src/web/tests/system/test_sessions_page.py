import httpx
from fastapi.testclient import TestClient
from legendarr_web.app import create_app

_SESSIONS = [
    {
        "id": 1,
        "created_at": "2026-08-20T10:00:00",
        "last_seen_at": "2026-08-26T09:00:00",
        "expires_at": "2026-09-25T10:00:00",
        "ip_address": "192.168.1.10",
        "user_agent": "pytest-current",
    },
    {
        "id": 2,
        "created_at": "2026-08-21T10:00:00",
        "last_seen_at": "2026-08-25T09:00:00",
        "expires_at": "2026-09-20T10:00:00",
        "ip_address": "192.168.1.20",
        "user_agent": "pytest-other",
    },
]


def _validate_result(session: dict | None) -> dict:
    return {"authenticated": True, "auth_enabled": True, "session": session}


def _handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/auth/sessions/validate":
        return httpx.Response(200, json=_validate_result(_SESSIONS[0]))
    if request.url.path == "/auth/sessions" and request.method == "GET":
        return httpx.Response(200, json=_SESSIONS)
    if request.url.path == "/auth/sessions/1":
        return httpx.Response(204)
    if request.url.path == "/auth/sessions/revoke-others":
        return httpx.Response(200, json={"revoked_count": 1})
    return httpx.Response(200, json=[])


def test_sessions_page_lists_sessions_and_flags_this_device(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_handler, stub_auth_validate=False)

    with TestClient(app) as client:
        response = client.get("/system/sessions/")

    assert response.status_code == 200
    assert "pytest-current" in response.text
    assert "pytest-other" in response.text
    assert "This device" in response.text


def test_sessions_page_shows_empty_state_with_no_sessions(stub_backend_client):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/auth/sessions/validate":
            return httpx.Response(200, json=_validate_result(None))
        if request.url.path == "/auth/sessions":
            return httpx.Response(200, json=[])
        return httpx.Response(200, json=[])

    app = create_app()
    stub_backend_client(app, handler=handler, stub_auth_validate=False)

    with TestClient(app) as client:
        response = client.get("/system/sessions/")

    assert response.status_code == 200
    assert "No active sessions." in response.text


def test_revoke_session_redirects_with_toast(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_handler, stub_auth_validate=False)

    with TestClient(app) as client:
        response = client.post("/system/sessions/1/revoke", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"].startswith("/system/sessions/?")
    assert "Session+revoked." in response.headers["location"]


def test_revoke_session_tolerates_already_gone_session(stub_backend_client):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/auth/sessions/validate":
            return httpx.Response(200, json=_validate_result(_SESSIONS[0]))
        if request.url.path == "/auth/sessions/999":
            return httpx.Response(404, json={"detail": "Session not found"})
        return httpx.Response(200, json=[])

    app = create_app()
    stub_backend_client(app, handler=handler, stub_auth_validate=False)

    with TestClient(app) as client:
        response = client.post("/system/sessions/999/revoke", follow_redirects=False)

    assert response.status_code == 303


def test_revoke_other_sessions_keeps_the_current_one(stub_backend_client):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/auth/sessions/validate":
            return httpx.Response(200, json=_validate_result(_SESSIONS[0]))
        if request.url.path == "/auth/sessions/revoke-others":
            calls.append(request.content)
            return httpx.Response(200, json={"revoked_count": 1})
        return httpx.Response(200, json=[])

    app = create_app()
    stub_backend_client(app, handler=handler, stub_auth_validate=False)

    with TestClient(app) as client:
        response = client.post("/system/sessions/revoke-others", follow_redirects=False)

    assert response.status_code == 303
    assert b'"keep_session_id":1' in calls[0]
