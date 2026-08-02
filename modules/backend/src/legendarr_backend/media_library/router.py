from collections.abc import Iterator

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session

from legendarr_backend.config.config_file import load_or_create_config_file
from legendarr_backend.config.settings import get_settings
from legendarr_backend.database.engine import get_session
from legendarr_backend.media_library.jobs import enqueue_full_scan, enqueue_media_sync
from legendarr_backend.media_library.list_media_library import list_movies, list_series
from legendarr_backend.media_library.schemas import MovieRead, SeriesRead

router = APIRouter(prefix="/media")


def _get_session() -> Iterator[Session]:
    with get_session() as session:
        yield session


@router.get("/movies", response_model=list[MovieRead])
def get_movies(session: Session = Depends(_get_session)) -> list[MovieRead]:
    return list_movies(session)


@router.get("/series", response_model=list[SeriesRead])
def get_series(session: Session = Depends(_get_session)) -> list[SeriesRead]:
    return list_series(session)


@router.post("/sync", status_code=202)
def trigger_media_sync(request: Request) -> dict[str, str]:
    """Enqueue an immediate library sync — same job body the periodic sync job runs.

    Shared by the web "Sync Now" button and the "sync after adding a connection" hook.
    """
    scheduler = getattr(request.app.state, "scheduler", None)
    if scheduler is None:
        raise HTTPException(status_code=503, detail="Scheduler is not running")
    config = load_or_create_config_file(get_settings())
    enqueue_media_sync(
        scheduler,
        retry_attempts=config.sync_retry_attempts,
        retry_delay_seconds=config.sync_retry_delay_seconds,
    )
    return {"status": "enqueued"}


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
