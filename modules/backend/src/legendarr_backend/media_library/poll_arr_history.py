import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlmodel import Session, select

from legendarr_backend.arr_services.client_factory import build_client
from legendarr_backend.arr_services.manage_arr_service import list_enabled_arr_services
from legendarr_backend.arr_services.models import ArrService
from legendarr_backend.media_library.models import MEDIA_MODEL_BY_TYPE, Movie

logger = logging.getLogger(__name__)

# (media_kind, media_id) — the concrete enqueue call is injected by the job wiring,
# keeping this service independent of the scheduler.
EnqueueScan = Callable[[str, int], None]


@dataclass(frozen=True)
class PollResult:
    scans_enqueued: int


def poll_arr_history(
    session: Session,
    *,
    enqueue_scan: EnqueueScan,
    poll_interval_minutes: int,
) -> PollResult:
    """Enqueue scans for items each connection's history reports as recently imported.

    Covers setups without the Arr webhook configured, without waiting for the full
    library scan. `since` reaches back two poll intervals so one missed run is still
    covered; rescans are idempotent and deduped per item, so the overlap is cheap.
    Items the history reports but the sync hasn't persisted yet are skipped — the
    next sync + poll picks them up. A failing connection never blocks the others.
    """
    since = datetime.now(UTC) - timedelta(minutes=2 * poll_interval_minutes)
    enqueued = 0
    for arr_service in list_enabled_arr_services(session):
        try:
            enqueued += _poll_service(session, arr_service, since, enqueue_scan)
        except Exception:
            logger.exception(
                "history poll failed for connection %r (%s)",
                arr_service.name,
                arr_service.service_type,
            )
    return PollResult(scans_enqueued=enqueued)


def _poll_service(
    session: Session,
    arr_service: ArrService,
    since: datetime,
    enqueue_scan: EnqueueScan,
) -> int:
    client = build_client(arr_service)
    try:
        imported_ids = client.list_recent_import_ids(since)
    finally:
        client.close()
    if not imported_ids:
        return 0
    model = MEDIA_MODEL_BY_TYPE[arr_service.service_type]
    rows = session.exec(
        select(model).where(
            model.arr_service_id == arr_service.id,
            model.arr_id.in_(imported_ids),
        )
    ).all()
    media_kind = "movie" if model is Movie else "series"
    for row in rows:
        enqueue_scan(media_kind, row.id)
    return len(rows)
