import logging
from collections.abc import Iterator
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session, select

from legendarr_backend.arr_services.models import ArrService
from legendarr_backend.config.config_file import load_or_create_config_file
from legendarr_backend.config.settings import get_settings
from legendarr_backend.database.engine import get_session
from legendarr_backend.media_library.jobs import enqueue_media_scan
from legendarr_backend.media_library.models import MEDIA_MODEL_BY_TYPE, Movie
from legendarr_backend.media_library.scan_media_files import delete_media_files
from legendarr_backend.scheduling.queues import JobQueue

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks")

_SCAN_EVENTS = {"Download", "Rename"}
_DELETE_EVENTS = {"MovieDelete", "SeriesDelete", "MovieFileDelete", "EpisodeFileDelete"}
_ITEM_KEY_BY_TYPE = {"radarr": "movie", "sonarr": "series"}


def _get_session() -> Iterator[Session]:
    with get_session() as session:
        yield session


@router.post("/arr/{arr_service_id}", status_code=204)
def receive_arr_webhook(
    arr_service_id: int,
    payload: dict[str, Any],
    request: Request,
    session: Session = Depends(_get_session),
) -> None:
    """Receive a Radarr/Sonarr "Connect" webhook and react to library changes.

    Unauthenticated: Arr webhook connections can't send custom headers, so the
    per-connection URL is the whole contract — the usual convention for LAN media
    tools. Events that don't change files on disk (Grab, Test, ...) are acknowledged
    and ignored, so Arr's "Test" button and future event types never error.

    `Download`/`Rename` cascade all the way through subtitle discovery, acquisition,
    and translation for the item — not just a rescan — so a freshly imported file gets
    translated immediately instead of waiting for the next periodic fan-out.
    """
    scheduler = getattr(request.app.state, "scheduler", None)
    on_cascade = getattr(request.app.state, "cascade_subtitle_scan", None)
    if scheduler is None or on_cascade is None:
        raise HTTPException(status_code=503, detail="Scheduler is not running")

    arr_service = session.get(ArrService, arr_service_id)
    if arr_service is None:
        raise HTTPException(status_code=404, detail="Unknown connection")

    event_type = payload.get("eventType")
    if event_type not in _SCAN_EVENTS | _DELETE_EVENTS:
        logger.debug("arr webhook %r ignored for connection %r", event_type, arr_service.name)
        return

    item_payload = payload.get(_ITEM_KEY_BY_TYPE[arr_service.service_type]) or {}
    arr_id = item_payload.get("id")
    if arr_id is None:
        logger.warning(
            "arr webhook %r without item id for connection %r",
            event_type,
            arr_service.name,
        )
        return

    model = MEDIA_MODEL_BY_TYPE[arr_service.service_type]
    item = session.exec(
        select(model).where(model.arr_service_id == arr_service_id, model.arr_id == arr_id)
    ).first()
    if item is None:
        # Arr is ahead of the sync — the next sync + full scan picks the item up.
        logger.info(
            "arr webhook %r for unknown %s %s — skipped",
            event_type,
            arr_service.service_type,
            arr_id,
        )
        return

    if event_type in _DELETE_EVENTS:
        # Rows are deleted directly instead of via rescan: the folder may already be
        # gone, and the rescan's unmounted-drive guard would keep stale rows.
        removed = delete_media_files(session, item)
        session.commit()
        logger.info("arr webhook %r: removed %d media files of %r", event_type, removed, item.title)
        return

    if event_type == "Rename" and item_payload.get("path"):
        item.remote_path = item_payload["path"]
        session.add(item)
        session.commit()

    config = load_or_create_config_file(get_settings())
    enqueue_media_scan(
        scheduler,
        "movie" if model is Movie else "series",
        item.id,
        JobQueue.SCAN,
        retry_attempts=config.scan_retry_attempts,
        retry_delay_seconds=config.scan_retry_delay_seconds,
        cascade=True,
        on_cascade=on_cascade,
    )
