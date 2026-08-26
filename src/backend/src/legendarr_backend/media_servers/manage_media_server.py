from sqlalchemy.orm.attributes import flag_modified
from sqlmodel import Session, select

from legendarr_backend.media_servers.models import MEDIA_SERVER_KINDS, MediaServerConfig
from legendarr_backend.media_servers.schemas import MediaServerConfigInput


def ensure_media_servers_seeded(session: Session) -> None:
    """Insert a row for any server kind not yet in the table, so the catalog always has
    exactly one row per `MEDIA_SERVER_KINDS` entry. Safe to call on every startup —
    existing rows (and their credentials) are left untouched. New rows seed
    `enabled=False` (the model's default) — a server with no `base_url`/`token` yet
    shouldn't look "on".
    """
    existing_kinds = set(session.exec(select(MediaServerConfig.kind)).all())
    for kind in MEDIA_SERVER_KINDS:
        if kind not in existing_kinds:
            session.add(MediaServerConfig(kind=kind))
    session.commit()


def list_media_servers(session: Session) -> list[MediaServerConfig]:
    return list(session.exec(select(MediaServerConfig)).all())


def get_media_server(session: Session, server_id: int) -> MediaServerConfig | None:
    return session.get(MediaServerConfig, server_id)


def mark_connection_verified(session: Session, server: MediaServerConfig) -> None:
    if server.connection_verified:
        return
    server.connection_verified = True
    session.add(server)
    session.commit()


def update_media_server(
    session: Session, server_id: int, data: MediaServerConfigInput
) -> MediaServerConfig | None:
    server = session.get(MediaServerConfig, server_id)
    if server is None:
        return None
    for field, value in data.model_dump().items():
        setattr(server, field, value)
    # Force the encrypted field into the UPDATE even when unchanged, so a legacy
    # plaintext value read back by EncryptedString is re-encrypted on any edit.
    flag_modified(server, "token")
    session.add(server)
    session.commit()
    session.refresh(server)
    return server
