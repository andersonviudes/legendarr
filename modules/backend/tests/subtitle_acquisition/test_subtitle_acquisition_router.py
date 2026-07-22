from fastapi.testclient import TestClient
from legendarr_backend.api import create_api_app
from legendarr_backend.database.engine import get_session
from legendarr_backend.subtitle_acquisition.manage_subtitle_provider import (
    ensure_subtitle_providers_seeded,
    get_subtitle_provider,
)
from legendarr_backend.subtitle_acquisition.models import SUBTITLE_PROVIDER_KINDS


def _seed() -> None:
    with get_session() as session:
        ensure_subtitle_providers_seeded(session)


def test_list_providers_returns_empty_list_on_fresh_db(isolated_database):
    with TestClient(create_api_app()) as client:
        response = client.get("/subtitle-providers/")

    assert response.status_code == 200
    assert response.json() == []


def test_list_providers_returns_seeded_catalog(isolated_database):
    with TestClient(create_api_app()) as client:
        _seed()
        response = client.get("/subtitle-providers/")

    assert response.status_code == 200
    kinds = {provider["kind"] for provider in response.json()}
    assert kinds == set(SUBTITLE_PROVIDER_KINDS)


def test_get_provider_returns_404_when_missing(isolated_database):
    with TestClient(create_api_app()) as client:
        assert client.get("/subtitle-providers/1").status_code == 404


def test_update_provider_sets_fields(isolated_database):
    with TestClient(create_api_app()) as client:
        _seed()
        provider_id = client.get("/subtitle-providers/").json()[0]["id"]

        response = client.patch(
            f"/subtitle-providers/{provider_id}", json={"enabled": False, "api_key": "key-1"}
        )

        assert response.status_code == 200
        assert response.json()["enabled"] is False


def test_update_provider_returns_404_when_missing(isolated_database):
    with TestClient(create_api_app()) as client:
        response = client.patch("/subtitle-providers/1", json={"enabled": False})

    assert response.status_code == 404


def test_update_with_blank_secret_keeps_existing(isolated_database):
    with TestClient(create_api_app()) as client:
        _seed()
        provider_id = client.get("/subtitle-providers/").json()[0]["id"]
        client.patch(f"/subtitle-providers/{provider_id}", json={"api_key": "key-1"})

        response = client.patch(f"/subtitle-providers/{provider_id}", json={"api_key": ""})

        assert response.status_code == 200
        with get_session() as session:
            assert get_subtitle_provider(session, provider_id).api_key == "key-1"


def test_search_options_default_to_bazarr_matching_values(isolated_database):
    with TestClient(create_api_app()) as client:
        _seed()
        opensubtitles = next(
            p for p in client.get("/subtitle-providers/").json() if p["kind"] == "opensubtitles"
        )

        assert opensubtitles["use_hash"] is True
        assert opensubtitles["include_ai_translated"] is False
        assert opensubtitles["include_machine_translated"] is False


def test_update_search_options_persists_and_survives_an_unrelated_patch(isolated_database):
    """A PATCH that only touches `enabled` (the toggle route) must not reset the search
    options back to their schema default, the same guarantee `username` already has."""
    with TestClient(create_api_app()) as client:
        _seed()
        provider_id = client.get("/subtitle-providers/").json()[0]["id"]
        client.patch(
            f"/subtitle-providers/{provider_id}",
            json={"use_hash": False, "include_ai_translated": True},
        )

        response = client.patch(f"/subtitle-providers/{provider_id}", json={"enabled": False})

        assert response.status_code == 200
        assert response.json()["use_hash"] is False
        assert response.json()["include_ai_translated"] is True
        assert response.json()["include_machine_translated"] is False


def test_is_configured_reflects_whether_the_required_credential_is_set(isolated_database):
    with TestClient(create_api_app()) as client:
        _seed()
        providers = client.get("/subtitle-providers/").json()
        opensubtitles_id = next(p["id"] for p in providers if p["kind"] == "opensubtitles")
        napiprojekt = next(p for p in providers if p["kind"] == "napiprojekt")

        assert next(p for p in providers if p["kind"] == "opensubtitles")["is_configured"] is False
        assert napiprojekt["is_configured"] is False  # needs a successful "Test connection" first

        response = client.patch(
            f"/subtitle-providers/{opensubtitles_id}", json={"api_key": "key-1"}
        )

        assert response.json()["is_configured"] is True


def test_is_configured_becomes_true_after_a_successful_test_for_a_credential_less_provider(
    isolated_database, monkeypatch
):
    monkeypatch.setattr(
        "legendarr_backend.subtitle_acquisition.router.test_connection",
        lambda config: (True, "Site is reachable"),
    )
    with TestClient(create_api_app()) as client:
        _seed()
        providers = client.get("/subtitle-providers/").json()
        napiprojekt_id = next(p["id"] for p in providers if p["kind"] == "napiprojekt")

        client.post(f"/subtitle-providers/{napiprojekt_id}/test", json={})

        response = client.get(f"/subtitle-providers/{napiprojekt_id}")
        assert response.json()["is_configured"] is True


def test_update_without_enabled_keeps_existing_enabled_state(isolated_database):
    """A PATCH that never mentions `enabled` (the edit form only sends credentials)
    must not silently flip a disabled provider back on via the schema's default."""
    with TestClient(create_api_app()) as client:
        _seed()
        provider_id = client.get("/subtitle-providers/").json()[0]["id"]
        client.patch(f"/subtitle-providers/{provider_id}", json={"enabled": False})

        response = client.patch(f"/subtitle-providers/{provider_id}", json={"api_key": "key-1"})

        assert response.status_code == 200
        assert response.json()["enabled"] is False


def test_update_without_username_keeps_existing_username(isolated_database):
    """A PATCH that never mentions `username` (the enable/disable toggle only sends
    `enabled`) must not null out a stored username."""
    with TestClient(create_api_app()) as client:
        _seed()
        provider_id = client.get("/subtitle-providers/").json()[0]["id"]
        client.patch(f"/subtitle-providers/{provider_id}", json={"username": "me@example.com"})

        response = client.patch(f"/subtitle-providers/{provider_id}", json={"enabled": False})

        assert response.status_code == 200
        assert response.json()["username"] == "me@example.com"


def test_list_and_get_omit_secrets(isolated_database):
    with TestClient(create_api_app()) as client:
        _seed()
        provider_id = client.get("/subtitle-providers/").json()[0]["id"]
        client.patch(f"/subtitle-providers/{provider_id}", json={"api_key": "key-1"})

        list_response = client.get("/subtitle-providers/")
        get_response = client.get(f"/subtitle-providers/{provider_id}")

    assert "api_key" not in list_response.json()[0]
    assert "api_key" not in get_response.json()
    assert "password" not in get_response.json()


def test_test_connection_returns_success(isolated_database, monkeypatch):
    monkeypatch.setattr(
        "legendarr_backend.subtitle_acquisition.router.test_connection",
        lambda config: (True, "Connection successful"),
    )
    with TestClient(create_api_app()) as client:
        _seed()
        provider_id = client.get("/subtitle-providers/").json()[0]["id"]

        response = client.post(f"/subtitle-providers/{provider_id}/test", json={})

    assert response.status_code == 200
    assert response.json() == {"success": True, "message": "Connection successful"}


def test_test_connection_returns_404_when_missing(isolated_database):
    with TestClient(create_api_app()) as client:
        response = client.post("/subtitle-providers/1/test", json={})

    assert response.status_code == 404
