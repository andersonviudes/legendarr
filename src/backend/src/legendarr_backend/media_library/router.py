from collections.abc import Iterator

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session

from legendarr_backend.config.config_file import load_or_create_config_file
from legendarr_backend.config.settings import get_settings
from legendarr_backend.database.engine import get_session
from legendarr_backend.media_library.get_media_detail import get_movie_detail, get_series_detail
from legendarr_backend.media_library.jobs import (
    enqueue_full_scan,
    enqueue_media_scan,
    enqueue_media_sync,
)
from legendarr_backend.media_library.list_media_library import list_movies, list_series
from legendarr_backend.media_library.list_wanted_media import list_wanted_media
from legendarr_backend.media_library.models import MediaFile, MediaKind
from legendarr_backend.media_library.schemas import (
    MovieDetailRead,
    MovieRead,
    SeriesDetailRead,
    SeriesRead,
    WantedRead,
)
from legendarr_backend.scheduling.queues import JobQueue
from legendarr_backend.subtitle_discovery.models import Subtitle
from legendarr_backend.subtitle_timing_sync.jobs import enqueue_timing_sync
from legendarr_backend.subtitle_translation.jobs import enqueue_translation

router = APIRouter(prefix="/media")


def _get_session() -> Iterator[Session]:
    with get_session() as session:
        yield session


def _get_scheduler(request: Request):
    scheduler = getattr(request.app.state, "scheduler", None)
    if scheduler is None:
        raise HTTPException(status_code=503, detail="Scheduler is not running")
    return scheduler


def _get_on_cascade(request: Request):
    on_cascade = getattr(request.app.state, "cascade_subtitle_scan", None)
    if on_cascade is None:
        raise HTTPException(status_code=503, detail="Scheduler is not running")
    return on_cascade


@router.get("/movies", response_model=list[MovieRead])
def get_movies(session: Session = Depends(_get_session)) -> list[MovieRead]:
    return list_movies(session)


@router.get("/series", response_model=list[SeriesRead])
def get_series(session: Session = Depends(_get_session)) -> list[SeriesRead]:
    return list_series(session)


@router.get("/wanted", response_model=list[WantedRead])
def get_wanted(session: Session = Depends(_get_session)) -> list[WantedRead]:
    return list_wanted_media(session)


@router.get("/movies/{movie_id}", response_model=MovieDetailRead)
def get_movie(movie_id: int, session: Session = Depends(_get_session)) -> MovieDetailRead:
    detail = get_movie_detail(session, movie_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Movie not found")
    return detail


@router.get("/series/{series_id}", response_model=SeriesDetailRead)
def get_series_item(series_id: int, session: Session = Depends(_get_session)) -> SeriesDetailRead:
    detail = get_series_detail(session, series_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Series not found")
    return detail


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


@router.post("/movies/{movie_id}/scan", status_code=202)
def trigger_movie_scan(movie_id: int, request: Request) -> dict[str, str]:
    return _trigger_item_scan(request, "movie", movie_id)


@router.post("/series/{series_id}/scan", status_code=202)
def trigger_series_scan(series_id: int, request: Request) -> dict[str, str]:
    return _trigger_item_scan(request, "series", series_id)


def _trigger_item_scan(request: Request, kind: MediaKind, item_id: int) -> dict[str, str]:
    """ "Scan Disk" for one movie/series: rescans the item's files, then cascades into
    subtitle discovery, acquisition, and translation for every `MediaFile` the item has
    afterward — including a file the scan just discovered on disk.
    """
    scheduler = _get_scheduler(request)
    on_cascade = _get_on_cascade(request)
    config = load_or_create_config_file(get_settings())
    enqueue_media_scan(
        scheduler,
        kind,
        item_id,
        JobQueue.SCAN,
        retry_attempts=config.scan_retry_attempts,
        retry_delay_seconds=config.scan_retry_delay_seconds,
        cascade=True,
        on_cascade=on_cascade,
    )
    return {"status": "enqueued"}


@router.post("/files/{media_file_id}/translate", status_code=202)
def trigger_file_translation(
    media_file_id: int, request: Request, session: Session = Depends(_get_session)
) -> dict[str, str]:
    if session.get(MediaFile, media_file_id) is None:
        raise HTTPException(status_code=404, detail="Media file not found")
    scheduler = _get_scheduler(request)
    config = load_or_create_config_file(get_settings())
    enqueue_translation(
        scheduler,
        media_file_id,
        JobQueue.TRANSLATE,
        retry_attempts=config.translate_retry_attempts,
        retry_delay_seconds=config.translate_retry_delay_seconds,
        default_translation_provider=config.default_translation_provider,
    )
    return {"status": "enqueued"}


@router.post("/subtitles/{subtitle_id}/sync-timing", status_code=202)
def trigger_subtitle_timing_sync(
    subtitle_id: int, request: Request, session: Session = Depends(_get_session)
) -> dict[str, str]:
    if session.get(Subtitle, subtitle_id) is None:
        raise HTTPException(status_code=404, detail="Subtitle not found")
    scheduler = _get_scheduler(request)
    config = load_or_create_config_file(get_settings())
    enqueue_timing_sync(
        scheduler,
        subtitle_id,
        JobQueue.TIMING_SYNC,
        retry_attempts=config.timing_sync_retry_attempts,
        retry_delay_seconds=config.timing_sync_retry_delay_seconds,
        timeout_seconds=config.timing_sync_timeout_seconds,
    )
    return {"status": "enqueued"}
