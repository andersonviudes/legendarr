import logging
from dataclasses import dataclass

from sqlmodel import Session, select

from legendarr_backend.arr_clients.base import MediaItem
from legendarr_backend.arr_services.client_factory import build_client
from legendarr_backend.arr_services.manage_arr_service import list_enabled_arr_services
from legendarr_backend.arr_services.models import ArrService
from legendarr_backend.media_library.models import Movie, Series

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SyncResult:
    movies_synced: int
    series_synced: int


_MEDIA_MODEL_BY_TYPE = {"radarr": Movie, "sonarr": Series}


def sync_media_library(session: Session) -> SyncResult:
    """Pull the current libraries from every enabled Radarr/Sonarr connection and
    persist them.

    Each connection is synced in isolation — a failing server never rolls back what
    the others synced, and rows are keyed by `(arr_service_id, arr_id)` so multiple
    instances of the same app type never collide.
    """
    movies_synced = 0
    series_synced = 0
    for arr_service in list_enabled_arr_services(session):
        try:
            synced = _sync_service(session, arr_service)
            session.commit()
            if arr_service.service_type == "radarr":
                movies_synced += synced
            else:
                series_synced += synced
        except Exception:
            session.rollback()
            logger.exception(
                "media sync failed for connection %r (%s)",
                arr_service.name,
                arr_service.service_type,
            )
    return SyncResult(movies_synced=movies_synced, series_synced=series_synced)


def _sync_service(session: Session, arr_service: ArrService) -> int:
    client = build_client(arr_service)
    try:
        items = client.list_items()
    finally:
        client.close()
    model = _MEDIA_MODEL_BY_TYPE[arr_service.service_type]
    _replace_service_items(session, model, arr_service.id, items)
    return len(items)


def _replace_service_items(
    session: Session, model: type[Movie] | type[Series], arr_service_id: int, items: list[MediaItem]
) -> None:
    """Upsert what the connection reports now and delete what it stopped reporting —
    scoped to that connection, so other instances' rows are never touched."""
    existing = {
        row.arr_id: row
        for row in session.exec(select(model).where(model.arr_service_id == arr_service_id))
    }
    for item in items:
        row = existing.pop(item.id, None)
        if row is None:
            session.add(
                model(
                    arr_service_id=arr_service_id,
                    arr_id=item.id,
                    title=item.title,
                    remote_path=item.path,
                )
            )
        else:
            row.title = item.title
            row.remote_path = item.path
            session.add(row)
    for stale in existing.values():
        session.delete(stale)
