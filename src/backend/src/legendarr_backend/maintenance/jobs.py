import logging

from apscheduler.schedulers.background import BackgroundScheduler

from legendarr_backend.config.config_file import AppConfigFile
from legendarr_backend.database.engine import get_session
from legendarr_backend.maintenance.cleanup_temp_files import cleanup_orphaned_temp_files
from legendarr_backend.scheduling.queues import JobQueue
from legendarr_backend.scheduling.scheduler import register_job

logger = logging.getLogger(__name__)


def register_temp_file_cleanup_job(
    scheduler: BackgroundScheduler,
    config: AppConfigFile,
) -> None:
    """Register the periodic orphaned-temp-file sweep on the shared scheduler
    (ROADMAP.md 0.22.0) — see `cleanup_temp_files.cleanup_orphaned_temp_files` for what
    it catches (a hard kill mid-extraction/OCR/transcription/timing-sync) and why.
    Own queue/schedule: filesystem-only work, unrelated to any other periodic job.
    """

    def sweep() -> None:
        with get_session() as session:
            removed = cleanup_orphaned_temp_files(
                session, min_age_minutes=config.temp_file_cleanup_min_age_minutes
            )
        logger.info("temp file cleanup removed %d orphaned file(s)", removed)

    register_job(
        scheduler,
        sweep,
        queue=JobQueue.MAINTENANCE,
        job_id="maintenance_temp_file_cleanup",
        trigger="interval",
        minutes=config.temp_file_cleanup_interval_minutes,
        retry_attempts=config.temp_file_cleanup_retry_attempts,
        retry_delay_seconds=config.temp_file_cleanup_retry_delay_seconds,
        max_instances=config.temp_file_cleanup_max_instances,
        coalesce=config.temp_file_cleanup_coalesce,
    )
