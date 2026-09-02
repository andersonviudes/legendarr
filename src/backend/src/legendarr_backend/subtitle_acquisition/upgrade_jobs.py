import logging
from datetime import timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from sqlmodel import Session

from legendarr_backend.config.config_file import AppConfigFile
from legendarr_backend.database.engine import get_session
from legendarr_backend.media_library.locate import resolve_media_file_path
from legendarr_backend.media_library.models import MediaFile
from legendarr_backend.media_servers.notify_media_servers import (
    notify_media_servers_of_subtitle_write,
)
from legendarr_backend.scheduling.queues import JobQueue
from legendarr_backend.scheduling.retry import with_retry
from legendarr_backend.scheduling.scheduler import register_job
from legendarr_backend.subtitle_acquisition.jobs import media_file_ids_with_completed_scan
from legendarr_backend.subtitle_acquisition.upgrade_media_file_subtitle import (
    should_check_for_upgrade,
    upgrade_subtitle_for_media_file,
)

logger = logging.getLogger(__name__)


def register_subtitle_upgrade_job(
    scheduler: BackgroundScheduler,
    config: AppConfigFile,
) -> None:
    """Register the periodic upgrade fan-out on the shared scheduler.

    Own schedule/queue/retry policy (`upgrade_*`), fully independent of
    `subtitle_acquisition.jobs.register_acquisition_job` — acquisition only searches for a
    *missing* subtitle, this job only re-checks an *already-acquired* one for a
    better-scoring release, on its own daily-by-default cadence. Same shape as
    `media_metadata.jobs.register_metadata_refresh_job`.
    """

    def fan_out() -> None:
        with get_session() as session:
            enqueued = enqueue_full_upgrade_scan(
                scheduler,
                session,
                retry_attempts=config.upgrade_retry_attempts,
                retry_delay_seconds=config.upgrade_retry_delay_seconds,
                recheck_after=timedelta(minutes=config.upgrade_interval_minutes),
            )
        logger.info("upgrade fan-out enqueued: %d media files", enqueued)

    register_job(
        scheduler,
        fan_out,
        queue=JobQueue.UPGRADE_BULK,
        job_id="subtitle_upgrade_fanout",
        trigger="interval",
        minutes=config.upgrade_interval_minutes,
        retry_attempts=config.upgrade_retry_attempts,
        retry_delay_seconds=config.upgrade_retry_delay_seconds,
        max_instances=config.upgrade_max_instances,
        coalesce=config.upgrade_coalesce,
    )


def enqueue_full_upgrade_scan(
    scheduler: BackgroundScheduler,
    session: Session,
    *,
    retry_attempts: int,
    retry_delay_seconds: float,
    recheck_after: timedelta,
) -> int:
    """Enqueue an upgrade re-check for every subtitle-discovery-ready `MediaFile` on the
    bulk queue — the periodic counterpart to
    `subtitle_acquisition.jobs.enqueue_full_acquisition_scan`, reusing the same
    `media_file_ids_with_completed_scan` eligibility filter: upgrade needs discovery's
    `Subtitle` rows to find the current subtitle to replace, same reasoning as acquisition.
    """
    media_file_ids = media_file_ids_with_completed_scan(session)
    for media_file_id in media_file_ids:
        enqueue_upgrade(
            scheduler,
            media_file_id,
            JobQueue.UPGRADE_BULK,
            retry_attempts=retry_attempts,
            retry_delay_seconds=retry_delay_seconds,
            recheck_after=recheck_after,
        )
    return len(media_file_ids)


def enqueue_upgrade(
    scheduler: BackgroundScheduler,
    media_file_id: int,
    queue: JobQueue,
    *,
    retry_attempts: int,
    retry_delay_seconds: float,
    recheck_after: timedelta = timedelta(),
) -> None:
    """Enqueue an ad-hoc upgrade re-check of one `MediaFile` for immediate execution.

    Same one-off `"date"` trigger/`replace_existing` shape as
    `subtitle_acquisition.jobs.enqueue_acquisition` — a second enqueue for the same file
    racing a still-pending run collapses into one. No cascade: an upgrade replaces a
    subtitle in place without changing its language, so it never needs to chain into a
    translation run.

    `recheck_after` throttles `should_check_for_upgrade` below (default: no throttle,
    always check) — the periodic fan-out is the only caller that passes a real recheck
    window, matching its own interval.
    """
    job_id = f"subtitle_upgrade:{media_file_id}"

    def run_upgrade() -> None:
        with get_session() as session:
            media_file = session.get(MediaFile, media_file_id)
            if media_file is None:
                logger.info("upgrade skipped: media file %d no longer exists", media_file_id)
                return
            video_path = resolve_media_file_path(session, media_file)
            if video_path is None:
                logger.info(
                    "upgrade skipped: owner of media file %d no longer exists", media_file_id
                )
                return
            if not should_check_for_upgrade(session, media_file, recheck_after):
                return
            result = upgrade_subtitle_for_media_file(session, media_file, video_path)
            session.commit()
            logger.info("upgrade finished for media file %d: %s", media_file_id, result)
            if result.upgraded_language is not None:
                notify_media_servers_of_subtitle_write(session, video_path)

    wrapped = with_retry(
        run_upgrade, max_attempts=retry_attempts, delay_seconds=retry_delay_seconds
    )
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
