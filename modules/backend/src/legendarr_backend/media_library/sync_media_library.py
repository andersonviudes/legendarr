import logging
from dataclasses import dataclass

from sqlmodel import Session, select

from legendarr_backend.arr_clients.base import MediaItem
from legendarr_backend.arr_services.client_factory import build_client
from legendarr_backend.arr_services.manage_arr_service import list_enabled_arr_services
from legendarr_backend.arr_services.models import ArrService
from legendarr_backend.media_library.models import MEDIA_MODEL_BY_TYPE, Movie, Series
from legendarr_backend.media_metadata.fetch_metadata import fetch_metadata_for_new_items

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SyncResult:
    movies_synced: int
    series_synced: int


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
            synced, new_items = _sync_service(session, arr_service)
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
            continue
        try:
            if arr_service.service_type == "radarr":
                fetch_metadata_for_new_items(session, movies=new_items, series=[])
            else:
                fetch_metadata_for_new_items(session, movies=[], series=new_items)
        except Exception:
            # A metadata-source outage never fails the sync itself — the core
            # Radarr/Sonarr data above is already committed either way.
            logger.exception(
                "metadata fetch failed for connection %r (%s)",
                arr_service.name,
                arr_service.service_type,
            )
    return SyncResult(movies_synced=movies_synced, series_synced=series_synced)


def _sync_service(
    session: Session, arr_service: ArrService
) -> tuple[int, list[Movie] | list[Series]]:
    client = build_client(arr_service)
    try:
        items = client.list_items()
    finally:
        client.close()
    model = MEDIA_MODEL_BY_TYPE[arr_service.service_type]
    new_items = _replace_service_items(session, model, arr_service.id, items)
    return len(items), new_items


def _replace_service_items(
    session: Session, model: type[Movie] | type[Series], arr_service_id: int, items: list[MediaItem]
) -> list[Movie] | list[Series]:
    """Upsert what the connection reports now and delete what it stopped reporting —
    scoped to that connection, so other instances' rows are never touched. Returns the
    rows newly created this call, so the caller can fetch metadata only for those."""
    existing = {
        row.arr_id: row
        for row in session.exec(select(model).where(model.arr_service_id == arr_service_id))
    }
    new_rows = []
    for item in items:
        row = existing.pop(item.id, None)
        if row is None:
            row = model(
                arr_service_id=arr_service_id,
                arr_id=item.id,
                title=item.title,
                remote_path=item.path,
                tvdb_id=item.tvdb_id,
                imdb_id=item.imdb_id,
            )
            session.add(row)
            new_rows.append(row)
        else:
            row.title = item.title
            row.remote_path = item.path
            row.tvdb_id = item.tvdb_id
            row.imdb_id = item.imdb_id
            session.add(row)
    for stale in existing.values():
        session.delete(stale)
    return new_rows
