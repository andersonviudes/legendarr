import pytest
from fastapi.testclient import TestClient
from legendarr_backend.api import create_api_app
from legendarr_backend.authentication import api_guard
from legendarr_backend.authentication import router as authentication_router


@pytest.fixture
def api_client(isolated_database, monkeypatch):
    monkeypatch.setattr(authentication_router, "get_settings", lambda: isolated_database)
    monkeypatch.setattr(api_guard, "get_settings", lambda: isolated_database)
    with TestClient(create_api_app()) as client:
        yield client


def _enable_auth(client: TestClient) -> str:
    """Enable login and return the generated API key."""
    response = client.put(
        "/auth/settings", json={"enabled": True, "username": "admin", "password": "hunter2"}
    )
    return response.json()["api_key"]


def test_open_endpoint_when_auth_is_disabled(api_client):
    response = api_client.get("/language-profiles/")

    assert response.status_code == 200


def test_protected_endpoint_401s_without_credentials_when_auth_enabled(api_client):
    _enable_auth(api_client)

    response = api_client.get("/language-profiles/")

    assert response.status_code == 401


def test_protected_endpoint_allows_a_valid_api_key(api_client):
    api_key = _enable_auth(api_client)

    response = api_client.get("/language-profiles/", headers={"X-Api-Key": api_key})

    assert response.status_code == 200


def test_protected_endpoint_rejects_a_wrong_api_key(api_client):
    _enable_auth(api_client)

    response = api_client.get("/language-profiles/", headers={"X-Api-Key": "wrong-key"})

    assert response.status_code == 401


def test_protected_endpoint_allows_a_valid_forwarded_session(api_client):
    _enable_auth(api_client)
    token = api_client.post(
        "/auth/login", json={"username": "admin", "password": "hunter2"}
    ).json()["token"]

    response = api_client.get("/language-profiles/", headers={"X-Legendarr-Session": token})

    assert response.status_code == 200


def test_protected_endpoint_rejects_an_unknown_session(api_client):
    _enable_auth(api_client)

    response = api_client.get(
        "/language-profiles/", headers={"X-Legendarr-Session": "not-a-real-token"}
    )

    assert response.status_code == 401


def test_webhooks_stay_open_even_when_auth_is_enabled(api_client):
    _enable_auth(api_client)

    # Radarr/Sonarr can't send any header — the request must reach the real handler
    # (which 503s here for lack of a running scheduler, `media_library/webhooks.py`'s
    # own concern, exercised in `test_webhooks.py`) rather than being 401'd by the gate.
    response = api_client.post("/webhooks/arr/999", json={"eventType": "Test"})

    assert response.status_code != 401


def test_auth_bootstrap_endpoints_stay_open_even_when_auth_is_enabled(api_client):
    _enable_auth(api_client)

    login_response = api_client.post(
        "/auth/login", json={"username": "admin", "password": "hunter2"}
    )
    validate_response = api_client.post("/auth/sessions/validate", json={"token": "anything"})

    assert login_response.status_code == 200
    assert validate_response.status_code == 200


def test_settings_endpoint_requires_credentials_once_enabled(api_client):
    _enable_auth(api_client)

    response = api_client.get("/auth/settings")

    assert response.status_code == 401
