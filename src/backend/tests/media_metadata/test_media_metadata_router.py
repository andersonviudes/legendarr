from fastapi.testclient import TestClient
from legendarr_backend.api import create_api_app
from legendarr_backend.database.engine import get_session
from legendarr_backend.media_metadata.manage_metadata_provider import (
    ensure_metadata_providers_seeded,
    get_metadata_provider,
)
from legendarr_backend.media_metadata.models import MEDIA_METADATA_PROVIDER_KINDS


def _seed() -> None:
    with get_session() as session:
        ensure_metadata_providers_seeded(session)


def test_list_providers_returns_empty_list_on_fresh_db(isolated_database):
    with TestClient(create_api_app()) as client:
        response = client.get("/metadata-providers/")

    assert response.status_code == 200
    assert response.json() == []


def test_list_providers_returns_seeded_catalog(isolated_database):
    with TestClient(create_api_app()) as client:
        _seed()
        response = client.get("/metadata-providers/")

    assert response.status_code == 200
    body = response.json()
    assert {provider["kind"] for provider in body} == set(MEDIA_METADATA_PROVIDER_KINDS)
    assert all(provider["enabled"] for provider in body)


def test_get_provider_returns_404_when_missing(isolated_database):
    with TestClient(create_api_app()) as client:
        assert client.get("/metadata-providers/1").status_code == 404


def test_update_provider_sets_fields(isolated_database):
    with TestClient(create_api_app()) as client:
        _seed()
        provider_id = client.get("/metadata-providers/").json()[0]["id"]

        response = client.patch(
            f"/metadata-providers/{provider_id}", json={"enabled": False, "api_key": "key-1"}
        )

        assert response.status_code == 200
        assert response.json()["enabled"] is False
        assert response.json()["is_configured"] is True


def test_update_provider_returns_404_when_missing(isolated_database):
    with TestClient(create_api_app()) as client:
        response = client.patch("/metadata-providers/1", json={"enabled": False})

    assert response.status_code == 404


def test_update_with_blank_secret_keeps_existing(isolated_database):
    with TestClient(create_api_app()) as client:
        _seed()
        provider_id = client.get("/metadata-providers/").json()[0]["id"]
        client.patch(f"/metadata-providers/{provider_id}", json={"api_key": "key-1"})

        response = client.patch(f"/metadata-providers/{provider_id}", json={"api_key": ""})

        assert response.status_code == 200
        with get_session() as session:
            fetched = get_metadata_provider(session, provider_id)
            assert fetched is not None
            assert fetched.api_key == "key-1"
