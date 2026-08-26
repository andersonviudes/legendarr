import pytest
from fastapi.testclient import TestClient
from legendarr_backend.api import create_api_app
from legendarr_backend.authentication import router as authentication_router


@pytest.fixture
def api_client(isolated_database, monkeypatch):
    """A `TestClient` whose authentication router reads/writes `config.yaml` from the
    same `tmp_path` `isolated_database` already pointed the DB engine at."""
    monkeypatch.setattr(authentication_router, "get_settings", lambda: isolated_database)
    with TestClient(create_api_app()) as client:
        yield client


def _enable_auth(client: TestClient, username: str = "admin", password: str = "hunter2") -> dict:
    response = client.put(
        "/auth/settings", json={"enabled": True, "username": username, "password": password}
    )
    assert response.status_code == 200
    return response.json()


def test_login_with_valid_credentials_returns_a_token(api_client):
    _enable_auth(api_client)

    response = api_client.post("/auth/login", json={"username": "admin", "password": "hunter2"})

    assert response.status_code == 200
    assert response.json()["token"]


def test_login_with_wrong_password_is_rejected(api_client):
    _enable_auth(api_client)

    response = api_client.post("/auth/login", json={"username": "admin", "password": "wrong"})

    assert response.status_code == 401


def test_logout_revokes_the_session(api_client):
    _enable_auth(api_client)
    token = api_client.post(
        "/auth/login", json={"username": "admin", "password": "hunter2"}
    ).json()["token"]

    logout_response = api_client.post("/auth/logout", json={"token": token})
    validate_response = api_client.post("/auth/sessions/validate", json={"token": token})

    assert logout_response.status_code == 204
    assert validate_response.json()["authenticated"] is False


def test_validate_session_when_auth_disabled_is_always_authenticated(api_client):
    response = api_client.post("/auth/sessions/validate", json={"token": None})

    assert response.json() == {"authenticated": True, "auth_enabled": False, "session": None}


def test_validate_session_with_a_valid_token(api_client):
    _enable_auth(api_client)
    token = api_client.post(
        "/auth/login", json={"username": "admin", "password": "hunter2"}
    ).json()["token"]

    response = api_client.post("/auth/sessions/validate", json={"token": token})

    payload = response.json()
    assert payload["authenticated"] is True
    assert payload["auth_enabled"] is True
    assert payload["session"]["id"]


def test_validate_session_with_an_unknown_token(api_client):
    _enable_auth(api_client)

    response = api_client.post("/auth/sessions/validate", json={"token": "not-a-real-token"})

    assert response.json()["authenticated"] is False


def test_get_sessions_lists_logged_in_sessions(api_client):
    _enable_auth(api_client)
    api_client.post("/auth/login", json={"username": "admin", "password": "hunter2"})

    response = api_client.get("/auth/sessions")

    assert response.status_code == 200
    assert len(response.json()) == 1


def test_delete_session_revokes_it(api_client):
    _enable_auth(api_client)
    api_client.post("/auth/login", json={"username": "admin", "password": "hunter2"})
    session_id = api_client.get("/auth/sessions").json()[0]["id"]

    response = api_client.delete(f"/auth/sessions/{session_id}")

    assert response.status_code == 204
    assert api_client.get("/auth/sessions").json() == []


def test_delete_session_returns_404_when_missing(api_client):
    response = api_client.delete("/auth/sessions/999")

    assert response.status_code == 404


def test_revoke_other_sessions_keeps_only_the_named_session(api_client):
    _enable_auth(api_client)
    api_client.post("/auth/login", json={"username": "admin", "password": "hunter2"})
    api_client.post("/auth/login", json={"username": "admin", "password": "hunter2"})
    sessions = api_client.get("/auth/sessions").json()
    keep_id = sessions[0]["id"]

    response = api_client.post("/auth/sessions/revoke-others", json={"keep_session_id": keep_id})

    assert response.json() == {"revoked_count": 1}
    remaining = api_client.get("/auth/sessions").json()
    assert [s["id"] for s in remaining] == [keep_id]


def test_get_settings_returns_defaults(api_client):
    response = api_client.get("/auth/settings")

    assert response.json() == {"enabled": False, "username": "", "api_key": ""}


def test_put_settings_rejects_enabling_without_credentials(api_client):
    response = api_client.put(
        "/auth/settings", json={"enabled": True, "username": "", "password": ""}
    )

    assert response.status_code == 400


def test_put_settings_enabling_generates_an_api_key(api_client):
    payload = _enable_auth(api_client)

    assert payload["enabled"] is True
    assert payload["username"] == "admin"
    assert payload["api_key"]


def test_regenerate_api_key_changes_the_stored_key(api_client):
    first = _enable_auth(api_client)

    response = api_client.post("/auth/settings/api-key/regenerate")

    assert response.status_code == 200
    assert response.json()["api_key"] != first["api_key"]
