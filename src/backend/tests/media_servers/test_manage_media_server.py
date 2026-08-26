from legendarr_backend.media_servers.manage_media_server import (
    ensure_media_servers_seeded,
    get_media_server,
    list_media_servers,
    mark_connection_verified,
    update_media_server,
)
from legendarr_backend.media_servers.models import MEDIA_SERVER_KINDS
from legendarr_backend.media_servers.schemas import MediaServerConfigInput
from legendarr_backend.security.secrets import ENCRYPTED_PREFIX
from sqlalchemy import text


def test_ensure_media_servers_seeded_creates_one_row_per_kind(in_memory_session):
    ensure_media_servers_seeded(in_memory_session)

    servers = list_media_servers(in_memory_session)

    assert {server.kind for server in servers} == set(MEDIA_SERVER_KINDS)
    # Unlike metadata providers, neither kind seeds enabled — a server with no
    # base_url/token yet shouldn't look "on".
    assert all(not server.enabled for server in servers)


def test_ensure_media_servers_seeded_is_idempotent(in_memory_session):
    ensure_media_servers_seeded(in_memory_session)
    ensure_media_servers_seeded(in_memory_session)

    servers = list_media_servers(in_memory_session)

    assert len(servers) == len(MEDIA_SERVER_KINDS)


def test_ensure_media_servers_seeded_keeps_existing_credentials(in_memory_session):
    ensure_media_servers_seeded(in_memory_session)
    server = next(s for s in list_media_servers(in_memory_session) if s.kind == "plex")
    assert server.id is not None
    update_media_server(
        in_memory_session,
        server.id,
        MediaServerConfigInput(base_url="http://plex.local:32400", token="my-token"),
    )

    ensure_media_servers_seeded(in_memory_session)

    refreshed = get_media_server(in_memory_session, server.id)
    assert refreshed is not None
    assert refreshed.token == "my-token"


def test_get_media_server_returns_none_when_missing(in_memory_session):
    assert get_media_server(in_memory_session, 1) is None


def test_mark_connection_verified_sets_the_flag(in_memory_session):
    ensure_media_servers_seeded(in_memory_session)
    server = list_media_servers(in_memory_session)[0]
    assert server.id is not None

    mark_connection_verified(in_memory_session, server)

    refreshed = get_media_server(in_memory_session, server.id)
    assert refreshed is not None
    assert refreshed.connection_verified is True


def test_update_media_server_replaces_fields(in_memory_session):
    ensure_media_servers_seeded(in_memory_session)
    server = list_media_servers(in_memory_session)[0]
    assert server.id is not None

    updated = update_media_server(
        in_memory_session,
        server.id,
        MediaServerConfigInput(
            enabled=True, base_url="http://plex.local:32400", token="secret-token"
        ),
    )

    assert updated is not None
    assert updated.enabled is True
    assert updated.base_url == "http://plex.local:32400"
    assert updated.token == "secret-token"


def test_update_media_server_returns_none_when_missing(in_memory_session):
    assert update_media_server(in_memory_session, 1, MediaServerConfigInput()) is None


def test_secrets_are_encrypted_at_rest(in_memory_session):
    ensure_media_servers_seeded(in_memory_session)
    server = list_media_servers(in_memory_session)[0]
    assert server.id is not None

    update_media_server(in_memory_session, server.id, MediaServerConfigInput(token="secret-token"))

    row = in_memory_session.execute(
        text("SELECT token FROM mediaserverconfig WHERE id = :id"), {"id": server.id}
    ).one()

    assert row.token.startswith(ENCRYPTED_PREFIX)
    assert "secret-token" not in row.token
