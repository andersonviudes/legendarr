from fastapi.testclient import TestClient
from legendarr_backend.api import create_api_app
from legendarr_backend.database.engine import get_session
from legendarr_backend.subtitle_translation.manage_translation_provider import (
    ensure_translation_providers_seeded,
    get_translation_provider,
)
from legendarr_backend.subtitle_translation.models import TRANSLATION_PROVIDER_KINDS


def _seed() -> None:
    with get_session() as session:
        ensure_translation_providers_seeded(session)


def test_list_providers_returns_empty_list_on_fresh_db(isolated_database):
    with TestClient(create_api_app()) as client:
        response = client.get("/translation-providers/")

    assert response.status_code == 200
    assert response.json() == []


def test_list_providers_returns_seeded_catalog(isolated_database):
    with TestClient(create_api_app()) as client:
        _seed()
        response = client.get("/translation-providers/")

    assert response.status_code == 200
    kinds = {provider["kind"] for provider in response.json()}
    assert kinds == set(TRANSLATION_PROVIDER_KINDS)


def test_get_provider_returns_404_when_missing(isolated_database):
    with TestClient(create_api_app()) as client:
        assert client.get("/translation-providers/1").status_code == 404


def test_update_provider_sets_fields(isolated_database):
    with TestClient(create_api_app()) as client:
        _seed()
        provider_id = client.get("/translation-providers/").json()[0]["id"]

        response = client.patch(
            f"/translation-providers/{provider_id}", json={"enabled": False, "api_key": "key-1"}
        )

        assert response.status_code == 200
        assert response.json()["enabled"] is False


def test_update_provider_returns_404_when_missing(isolated_database):
    with TestClient(create_api_app()) as client:
        response = client.patch("/translation-providers/1", json={"enabled": False})

    assert response.status_code == 404


def test_update_with_blank_secret_keeps_existing(isolated_database):
    with TestClient(create_api_app()) as client:
        _seed()
        provider_id = client.get("/translation-providers/").json()[0]["id"]
        client.patch(f"/translation-providers/{provider_id}", json={"api_key": "key-1"})

        response = client.patch(f"/translation-providers/{provider_id}", json={"api_key": ""})

        assert response.status_code == 200
        with get_session() as session:
            fetched = get_translation_provider(session, provider_id)
            assert fetched is not None
            assert fetched.api_key == "key-1"


def test_update_without_enabled_keeps_existing_enabled_state(isolated_database):
    """A PATCH that never mentions `enabled` (the edit form only sends credentials)
    must not silently flip a disabled provider back on via the schema's default."""
    with TestClient(create_api_app()) as client:
        _seed()
        provider_id = client.get("/translation-providers/").json()[0]["id"]
        client.patch(f"/translation-providers/{provider_id}", json={"enabled": False})

        response = client.patch(f"/translation-providers/{provider_id}", json={"api_key": "key-1"})

        assert response.status_code == 200
        assert response.json()["enabled"] is False


def test_update_without_endpoint_keeps_existing_endpoint(isolated_database):
    """A PATCH that never mentions `endpoint` (the enable/disable toggle only sends
    `enabled`) must not null out a stored endpoint."""
    with TestClient(create_api_app()) as client:
        _seed()
        provider_id = next(
            p["id"]
            for p in client.get("/translation-providers/").json()
            if p["kind"] == "libretranslate"
        )
        client.patch(
            f"/translation-providers/{provider_id}",
            json={"endpoint": "http://localhost:5000"},
        )

        response = client.patch(f"/translation-providers/{provider_id}", json={"enabled": False})

        assert response.status_code == 200
        assert response.json()["endpoint"] == "http://localhost:5000"


def test_update_without_model_keeps_existing_model(isolated_database):
    """A PATCH that never mentions `model` (the enable/disable toggle only sends
    `enabled`) must not null out a stored model."""
    with TestClient(create_api_app()) as client:
        _seed()
        provider_id = next(
            p["id"] for p in client.get("/translation-providers/").json() if p["kind"] == "llm"
        )
        client.patch(f"/translation-providers/{provider_id}", json={"model": "gpt-4o"})

        response = client.patch(f"/translation-providers/{provider_id}", json={"enabled": False})

        assert response.status_code == 200
        assert response.json()["model"] == "gpt-4o"


def test_is_configured_reflects_whether_the_required_credential_is_set(isolated_database):
    with TestClient(create_api_app()) as client:
        _seed()
        providers = client.get("/translation-providers/").json()
        deepl_id = next(p["id"] for p in providers if p["kind"] == "deepl")

        assert next(p for p in providers if p["kind"] == "deepl")["is_configured"] is False

        response = client.patch(f"/translation-providers/{deepl_id}", json={"api_key": "key-1"})

        assert response.json()["is_configured"] is True


def test_list_and_get_omit_secrets(isolated_database):
    with TestClient(create_api_app()) as client:
        _seed()
        provider_id = client.get("/translation-providers/").json()[0]["id"]
        client.patch(f"/translation-providers/{provider_id}", json={"api_key": "key-1"})

        list_response = client.get("/translation-providers/")
        get_response = client.get(f"/translation-providers/{provider_id}")

    assert "api_key" not in list_response.json()[0]
    assert "api_key" not in get_response.json()


def test_test_connection_returns_success(isolated_database, monkeypatch):
    monkeypatch.setattr(
        "legendarr_backend.subtitle_translation.router.test_connection",
        lambda config: (True, "Connection successful"),
    )
    with TestClient(create_api_app()) as client:
        _seed()
        provider_id = client.get("/translation-providers/").json()[0]["id"]

        response = client.post(f"/translation-providers/{provider_id}/test", json={})

    assert response.status_code == 200
    assert response.json() == {"success": True, "message": "Connection successful"}


def test_test_connection_returns_404_when_missing(isolated_database):
    with TestClient(create_api_app()) as client:
        response = client.post("/translation-providers/1/test", json={})

    assert response.status_code == 404
