from collections.abc import Iterator

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from legendarr_backend.database.engine import get_session
from legendarr_backend.media_servers.connection_tests import test_connection
from legendarr_backend.media_servers.manage_media_server import (
    get_media_server,
    list_media_servers,
    mark_connection_verified,
    update_media_server,
)
from legendarr_backend.media_servers.models import MediaServerConfig
from legendarr_backend.media_servers.schemas import MediaServerConfigInput, MediaServerConfigRead

router = APIRouter(prefix="/media-servers", tags=["Media Servers"])


def _get_session() -> Iterator[Session]:
    with get_session() as session:
        yield session


def _merge_with_existing(
    data: MediaServerConfigInput, existing: MediaServerConfig
) -> MediaServerConfigInput:
    """A blank secret means "keep the current one"; a field the request never sent at
    all means "don't touch it" — same reasoning as `media_metadata/router.py`."""
    provided = data.model_fields_set
    return data.model_copy(
        update={
            "enabled": data.enabled if "enabled" in provided else existing.enabled,
            "base_url": data.base_url if "base_url" in provided else existing.base_url,
            "token": data.token or existing.token,
        }
    )


@router.get("/", response_model=list[MediaServerConfigRead])
def list_servers(session: Session = Depends(_get_session)) -> list[MediaServerConfig]:
    return list_media_servers(session)


@router.get("/{server_id}", response_model=MediaServerConfigRead)
def get_server(server_id: int, session: Session = Depends(_get_session)) -> MediaServerConfig:
    server = get_media_server(session, server_id)
    if server is None:
        raise HTTPException(status_code=404, detail="Media server not found")
    return server


@router.patch("/{server_id}", response_model=MediaServerConfigRead)
def update_server(
    server_id: int,
    data: MediaServerConfigInput,
    session: Session = Depends(_get_session),
) -> MediaServerConfig:
    existing = get_media_server(session, server_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Media server not found")
    server = update_media_server(session, server_id, _merge_with_existing(data, existing))
    assert server is not None
    return server


@router.post("/{server_id}/test")
def test_server_connection(
    server_id: int,
    data: MediaServerConfigInput,
    session: Session = Depends(_get_session),
) -> dict:
    existing = get_media_server(session, server_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Media server not found")
    merged = _merge_with_existing(data, existing)
    candidate = existing.model_copy(update=merged.model_dump())
    success, message = test_connection(candidate)
    if success:
        mark_connection_verified(session, existing)
    return {"success": success, "message": message}
