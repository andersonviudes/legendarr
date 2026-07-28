import logging
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from sqlmodel import Session, select

from legendarr_backend.arr_services.models import ArrService
from legendarr_backend.arr_services.path_mapping import resolve_local_path
from legendarr_backend.config.config_file import AppConfigFile
from legendarr_backend.database.engine import get_session
from legendarr_backend.media_library.models import MediaFile, Movie, Series
from legendarr_backend.scheduling.queues import JobQueue
from legendarr_backend.scheduling.retry import with_retry
from legendarr_backend.scheduling.scheduler import register_job
from legendarr_backend.subtitle_discovery.scan_media_subtitles import scan_subtitles_for_media_file

logger = logging.getLogger(__name__)


def register_subtitle_scan_job(
    scheduler: BackgroundScheduler,
    config: AppConfigFile,
) -> None:
    """Register the periodic subtitle-scan fan-out on the shared scheduler."""

    def fan_out() -> None:
        with get_session() as session:
            enqueued = enqueue_full_subtitle_scan(
                scheduler,
                session,
                retry_attempts=config.subtitle_scan_retry_attempts,
                retry_delay_seconds=config.subtitle_scan_retry_delay_seconds,
            )
        logger.info("subtitle scan fan-out enqueued: %d media files", enqueued)

    register_job(
        scheduler,
        fan_out,
        queue=JobQueue.SYNC,
        job_id="subtitle_discovery_scan_fanout",
        trigger="interval",
        minutes=config.subtitle_scan_interval_minutes,
        retry_attempts=config.subtitle_scan_retry_attempts,
        retry_delay_seconds=config.subtitle_scan_retry_delay_seconds,
        max_instances=config.subtitle_scan_max_instances,
        coalesce=config.subtitle_scan_coalesce,
    )


def enqueue_full_subtitle_scan(
    scheduler: BackgroundScheduler,
    session: Session,
    *,
    retry_attempts: int,
    retry_delay_seconds: float,
) -> int:
    """Enqueue a per-file subtitle scan for every known `MediaFile` on the bulk queue.

    Shared by the periodic fan-out job — same shape as media_library's
    `enqueue_full_scan`, kept a separate function for the same reason (reusable by a
    future manual-trigger endpoint without duplicating the fan-out logic).
    """
    media_file_ids = session.exec(select(MediaFile.id)).all()
    for media_file_id in media_file_ids:
        enqueue_subtitle_scan(
            scheduler,
            media_file_id,
            JobQueue.SCAN_BULK,
            retry_attempts=retry_attempts,
            retry_delay_seconds=retry_delay_seconds,
        )
    return len(media_file_ids)


def enqueue_subtitle_scan(
    scheduler: BackgroundScheduler,
    media_file_id: int,
    queue: JobQueue,
    *,
    retry_attempts: int,
    retry_delay_seconds: float,
) -> None:
    """Enqueue an ad-hoc subtitle scan of one `MediaFile` for immediate execution.

    Same `add_job` shape as `media_library.jobs.enqueue_media_scan`: a "date" trigger
    with `misfire_grace_time=None` and `replace_existing=True` dedupes a pending
    rescan of the same file.
    """

    def run_scan() -> None:
        with get_session() as session:
            media_file = session.get(MediaFile, media_file_id)
            if media_file is None:
                logger.info("subtitle scan skipped: media file %d no longer exists", media_file_id)
                return
            item, arr_service = _resolve_owner(session, media_file)
            if item is None or arr_service is None:
                logger.info(
                    "subtitle scan skipped: owner of media file %d no longer exists",
                    media_file_id,
                )
                return
            root = Path(resolve_local_path(arr_service, item.remote_path))
            result = scan_subtitles_for_media_file(
                session, media_file, root / media_file.relative_path
            )
            session.commit()
            logger.info("subtitle scan finished for media file %d: %s", media_file_id, result)

    scheduler.add_job(
        with_retry(run_scan, max_attempts=retry_attempts, delay_seconds=retry_delay_seconds),
        "date",
        id=f"subtitle_scan:{media_file_id}",
        name=f"subtitle_scan:{media_file_id}",
        executor=queue.value,
        max_instances=1,
        replace_existing=True,
        misfire_grace_time=None,
    )


def _resolve_owner(
    session: Session, media_file: MediaFile
) -> tuple[Movie | Series | None, ArrService | None]:
    if media_file.movie_id is not None:
        item = session.get(Movie, media_file.movie_id)
    else:
        item = session.get(Series, media_file.series_id)
    if item is None:
        return None, None
    return item, session.get(ArrService, item.arr_service_id)
