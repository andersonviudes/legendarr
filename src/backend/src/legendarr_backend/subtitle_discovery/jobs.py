import logging

from apscheduler.schedulers.background import BackgroundScheduler
from sqlmodel import Session, select

from legendarr_backend.config.config_file import AppConfigFile, load_or_create_config_file
from legendarr_backend.config.settings import get_settings
from legendarr_backend.database.engine import get_session
from legendarr_backend.media_library.locate import resolve_media_file_path
from legendarr_backend.media_library.models import MediaFile
from legendarr_backend.scheduling.queues import JobQueue
from legendarr_backend.scheduling.retry import with_retry
from legendarr_backend.scheduling.scheduler import register_job
from legendarr_backend.subtitle_acquisition.jobs import enqueue_acquisition
from legendarr_backend.subtitle_discovery.probe_embedded_subtitles import (
    DEFAULT_PROBE_TIMEOUT_SECONDS,
)
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
                probe_timeout_seconds=config.embedded_subtitle_probe_timeout_seconds,
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
    probe_timeout_seconds: float = DEFAULT_PROBE_TIMEOUT_SECONDS,
) -> int:
    """Enqueue a per-file subtitle scan for every known `MediaFile` on the bulk queue.

    Shared by the periodic fan-out job — same shape as media_library's
    `enqueue_full_scan`, kept a separate function for the same reason (reusable by a
    future manual-trigger endpoint without duplicating the fan-out logic).
    """
    media_file_ids = session.exec(select(MediaFile.id)).all()
    for media_file_id in media_file_ids:
        assert media_file_id is not None
        enqueue_subtitle_scan(
            scheduler,
            media_file_id,
            JobQueue.SCAN_BULK,
            retry_attempts=retry_attempts,
            retry_delay_seconds=retry_delay_seconds,
            probe_timeout_seconds=probe_timeout_seconds,
        )
    return len(media_file_ids)


def enqueue_subtitle_scan(
    scheduler: BackgroundScheduler,
    media_file_id: int,
    queue: JobQueue,
    *,
    retry_attempts: int,
    retry_delay_seconds: float,
    probe_timeout_seconds: float = DEFAULT_PROBE_TIMEOUT_SECONDS,
    cascade: bool = False,
) -> None:
    """Enqueue an ad-hoc subtitle scan of one `MediaFile` for immediate execution.

    Same `add_job` shape as `media_library.jobs.enqueue_media_scan`: a "date" trigger
    with `misfire_grace_time=None` and `replace_existing=True` dedupes a pending
    rescan of the same file.

    Same sticky-cascade merge as `enqueue_media_scan` too — a later, non-cascading
    enqueue (the bulk fan-out) must not silently swap out a still-pending cascade=True
    job (a scan's own cascade) racing the same file; the wrapped job function's own
    `cascade` attribute is read back via `scheduler.get_job` before scheduling.

    `cascade=True` chains into an acquisition run for the same file once this scan
    commits — opt-in, same reasoning as `enqueue_media_scan`'s `cascade`.
    """
    job_id = f"subtitle_scan:{media_file_id}"
    pending = scheduler.get_job(job_id)
    if pending is not None and getattr(pending.func, "cascade", False):
        cascade = True

    def run_scan() -> None:
        with get_session() as session:
            media_file = session.get(MediaFile, media_file_id)
            if media_file is None:
                logger.info("subtitle scan skipped: media file %d no longer exists", media_file_id)
                return
            video_path = resolve_media_file_path(session, media_file)
            if video_path is None:
                logger.info(
                    "subtitle scan skipped: owner of media file %d no longer exists",
                    media_file_id,
                )
                return
            result = scan_subtitles_for_media_file(
                session, media_file, video_path, probe_timeout_seconds=probe_timeout_seconds
            )
            session.commit()
            logger.info("subtitle scan finished for media file %d: %s", media_file_id, result)
            if cascade:
                config = load_or_create_config_file(get_settings())
                enqueue_acquisition(
                    scheduler,
                    media_file_id,
                    JobQueue.ACQUIRE,
                    retry_attempts=config.acquisition_retry_attempts,
                    retry_delay_seconds=config.acquisition_retry_delay_seconds,
                    cascade=True,
                )

    wrapped = with_retry(run_scan, max_attempts=retry_attempts, delay_seconds=retry_delay_seconds)
    setattr(wrapped, "cascade", cascade)  # noqa: B010 — direct assignment fails pyright
    scheduler.add_job(
        wrapped,
        "date",
        id=job_id,
        name=job_id,
        executor=queue.value,
        max_instances=1,
        replace_existing=True,
        misfire_grace_time=None,
    )
