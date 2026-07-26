import logging
from functools import partial
from typing import Literal

from apscheduler.schedulers.background import BackgroundScheduler
from sqlmodel import Session, select

from legendarr_backend.arr_services.models import ArrService
from legendarr_backend.config.config_file import AppConfigFile
from legendarr_backend.database.engine import get_session
from legendarr_backend.media_library.models import Movie, Series
from legendarr_backend.media_library.poll_arr_history import poll_arr_history
from legendarr_backend.media_library.scan_media_files import scan_media_item
from legendarr_backend.media_library.sync_media_library import sync_media_library
from legendarr_backend.scheduling.queues import JobQueue
from legendarr_backend.scheduling.retry import with_retry
from legendarr_backend.scheduling.scheduler import register_job

logger = logging.getLogger(__name__)

MediaKind = Literal["movie", "series"]


def register_sync_job(
    scheduler: BackgroundScheduler,
    config: AppConfigFile,
) -> None:
    """Register the periodic media library sync job on the shared scheduler."""

    def run_sync() -> None:
        with get_session() as session:
            result = sync_media_library(session)
        logger.info("media library synced: %s", result)

    register_job(
        scheduler,
        run_sync,
        queue=JobQueue.SYNC,
        job_id="media_library_sync",
        trigger="interval",
        minutes=config.sync_interval_minutes,
        retry_attempts=config.sync_retry_attempts,
        retry_delay_seconds=config.sync_retry_delay_seconds,
        max_instances=config.sync_max_instances,
        coalesce=config.sync_coalesce,
    )


def register_scan_job(
    scheduler: BackgroundScheduler,
    config: AppConfigFile,
) -> None:
    """Register the periodic full-library scan fan-out on the shared scheduler."""

    def fan_out() -> None:
        with get_session() as session:
            movies, series = enqueue_full_scan(
                scheduler,
                session,
                retry_attempts=config.scan_retry_attempts,
                retry_delay_seconds=config.scan_retry_delay_seconds,
            )
        logger.info("media scan fan-out enqueued: %d movies, %d series", movies, series)

    register_job(
        scheduler,
        fan_out,
        queue=JobQueue.SYNC,
        job_id="media_library_scan_fanout",
        trigger="interval",
        minutes=config.scan_interval_minutes,
        retry_attempts=config.scan_retry_attempts,
        retry_delay_seconds=config.scan_retry_delay_seconds,
        max_instances=config.scan_max_instances,
        coalesce=config.scan_coalesce,
    )


def enqueue_full_scan(
    scheduler: BackgroundScheduler,
    session: Session,
    *,
    retry_attempts: int,
    retry_delay_seconds: float,
) -> tuple[int, int]:
    """Enqueue a per-item scan for every synced movie/series on the bulk queue.

    Shared by the periodic fan-out job and the manual `POST /media/scan` endpoint.
    Returns `(movies_enqueued, series_enqueued)`.
    """
    enqueue = partial(
        enqueue_media_scan,
        scheduler,
        queue=JobQueue.SCAN_BULK,
        retry_attempts=retry_attempts,
        retry_delay_seconds=retry_delay_seconds,
    )
    movie_ids = session.exec(select(Movie.id)).all()
    series_ids = session.exec(select(Series.id)).all()
    for movie_id in movie_ids:
        enqueue("movie", movie_id)
    for series_id in series_ids:
        enqueue("series", series_id)
    return len(movie_ids), len(series_ids)


def register_history_poll_job(
    scheduler: BackgroundScheduler,
    config: AppConfigFile,
) -> None:
    """Register the periodic Arr history poll on the shared scheduler."""

    def run_poll() -> None:
        enqueue = partial(
            enqueue_media_scan,
            scheduler,
            queue=JobQueue.SCAN,
            retry_attempts=config.scan_retry_attempts,
            retry_delay_seconds=config.scan_retry_delay_seconds,
        )
        with get_session() as session:
            result = poll_arr_history(
                session,
                enqueue_scan=enqueue,
                poll_interval_minutes=config.history_poll_interval_minutes,
            )
        logger.info("arr history polled: %s", result)

    register_job(
        scheduler,
        run_poll,
        queue=JobQueue.SYNC,
        job_id="arr_history_poll",
        trigger="interval",
        minutes=config.history_poll_interval_minutes,
        retry_attempts=config.history_poll_retry_attempts,
        retry_delay_seconds=config.history_poll_retry_delay_seconds,
        max_instances=config.history_poll_max_instances,
        coalesce=config.history_poll_coalesce,
    )


def enqueue_media_scan(
    scheduler: BackgroundScheduler,
    media_kind: MediaKind,
    media_id: int,
    queue: JobQueue,
    *,
    retry_attempts: int,
    retry_delay_seconds: float,
) -> None:
    """Enqueue an ad-hoc scan of one media item for immediate execution.

    Shared by every scan trigger (interval fan-out, Arr webhook, history poll) so the
    enqueue policy lives in one place. `replace_existing` dedupes a pending rescan of
    the same item; an already-running scan is left alone — both runs diff against the
    database and the retry policy resolves a commit conflict. Uses `add_job` directly
    instead of `register_job` because of the date trigger with `misfire_grace_time=None`
    — the 1s default could silently drop event-triggered scans under load.
    """

    def run_scan() -> None:
        with get_session() as session:
            model = Movie if media_kind == "movie" else Series
            item = session.get(model, media_id)
            if item is None:
                logger.info("media scan skipped: %s %d no longer exists", media_kind, media_id)
                return
            arr_service = session.get(ArrService, item.arr_service_id)
            if arr_service is None:
                logger.info(
                    "media scan skipped: connection of %s %d no longer exists",
                    media_kind,
                    media_id,
                )
                return
            result = scan_media_item(session, item, arr_service)
            session.commit()
            logger.info("media scan finished for %r: %s", item.title, result)

    scheduler.add_job(
        with_retry(run_scan, max_attempts=retry_attempts, delay_seconds=retry_delay_seconds),
        "date",
        id=f"media_scan:{media_kind}:{media_id}",
        name=f"media_scan:{media_kind}:{media_id}",
        executor=queue.value,
        max_instances=1,
        replace_existing=True,
        misfire_grace_time=None,
    )
