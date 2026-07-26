from collections.abc import Iterator

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session

from legendarr_backend.config.config_file import load_or_create_config_file
from legendarr_backend.config.settings import get_settings
from legendarr_backend.database.engine import get_session
from legendarr_backend.media_library.jobs import enqueue_full_scan

router = APIRouter(prefix="/media")


def _get_session() -> Iterator[Session]:
    with get_session() as session:
        yield session


@router.post("/scan", status_code=202)
def trigger_media_scan(
    request: Request, session: Session = Depends(_get_session)
) -> dict[str, int]:
    """Enqueue a full-library scan fan-out — same shape as the periodic scan job."""
    scheduler = getattr(request.app.state, "scheduler", None)
    if scheduler is None:
        raise HTTPException(status_code=503, detail="Scheduler is not running")
    config = load_or_create_config_file(get_settings())
    movies, series = enqueue_full_scan(
        scheduler,
        session,
        retry_attempts=config.scan_retry_attempts,
        retry_delay_seconds=config.scan_retry_delay_seconds,
    )
    return {"movies_enqueued": movies, "series_enqueued": series}
