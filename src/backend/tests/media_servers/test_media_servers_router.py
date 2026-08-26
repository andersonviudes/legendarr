from fastapi.testclient import TestClient
from legendarr_backend.api import create_api_app
from legendarr_backend.database.engine import get_session
from legendarr_backend.media_servers.manage_media_server import (
    ensure_media_servers_seeded,
    get_media_server,
)
from legendarr_backend.media_servers.models import MEDIA_SERVER_KINDS


def _seed() -> None:
    with get_session() as session:
        ensure_media_servers_seeded(session)


def test_list_servers_returns_empty_list_on_fresh_db(isolated_database):
    with TestClient(create_api_app()) as client:
        response = client.get("/media-servers/")

    assert response.status_code == 200
    assert response.json() == []


def test_list_servers_returns_seeded_catalog(isolated_database):
    with TestClient(create_api_app()) as client:
        _seed()
        response = client.get("/media-servers/")

    assert response.status_code == 200
    body = response.json()
    assert {server["kind"] for server in body} == set(MEDIA_SERVER_KINDS)
    assert all(server["enabled"] is False for server in body)


def test_get_server_returns_404_when_missing(isolated_database):
    with TestClient(create_api_app()) as client:
        assert client.get("/media-servers/1").status_code == 404


def test_update_server_sets_fields(isolated_database):
    with TestClient(create_api_app()) as client:
        _seed()
        server_id = client.get("/media-servers/").json()[0]["id"]

        response = client.patch(
            f"/media-servers/{server_id}",
            json={"enabled": True, "base_url": "http://plex.local:32400", "token": "tok"},
        )

        assert response.status_code == 200
        assert response.json()["enabled"] is True
        assert response.json()["base_url"] == "http://plex.local:32400"
        assert response.json()["is_configured"] is True


def test_update_server_returns_404_when_missing(isolated_database):
    with TestClient(create_api_app()) as client:
        response = client.patch("/media-servers/1", json={"enabled": False})

    assert response.status_code == 404


def test_update_with_blank_secret_keeps_existing(isolated_database):
    with TestClient(create_api_app()) as client:
        _seed()
        server_id = client.get("/media-servers/").json()[0]["id"]
        client.patch(f"/media-servers/{server_id}", json={"token": "tok-1"})

        response = client.patch(f"/media-servers/{server_id}", json={"token": ""})

        assert response.status_code == 200
        with get_session() as session:
            fetched = get_media_server(session, server_id)
            assert fetched is not None
            assert fetched.token == "tok-1"


def test_update_with_blank_base_url_clears_it(isolated_database):
    """Unlike `token`, `base_url` isn't a secret — an explicit blank means "clear it,"
    same "field sent means take the value" rule `_merge_with_existing` applies to every
    non-secret field."""
    with TestClient(create_api_app()) as client:
        _seed()
        server_id = client.get("/media-servers/").json()[0]["id"]
        client.patch(f"/media-servers/{server_id}", json={"base_url": "http://plex.local:32400"})

        response = client.patch(f"/media-servers/{server_id}", json={"base_url": ""})

        assert response.status_code == 200
        assert response.json()["base_url"] == ""
