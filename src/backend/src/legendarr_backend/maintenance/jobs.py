import logging

from apscheduler.schedulers.background import BackgroundScheduler

from legendarr_backend.config.config_file import AppConfigFile
from legendarr_backend.database.engine import get_session
from legendarr_backend.maintenance.cleanup_temp_files import cleanup_orphaned_temp_files
from legendarr_backend.maintenance.reap_stuck_tasks import reap_stuck_tasks
from legendarr_backend.scheduling.queues import JobQueue
from legendarr_backend.scheduling.scheduler import register_job

logger = logging.getLogger(__name__)

# How often the stuck-task sweep runs, and the retry/concurrency policy it runs under.
# Module constants rather than config fields, unlike every other job here: this is an
# internal safety net for the execution budget failing to fire, not a behavior anyone
# would want to tune — same posture as `scheduling/circuit_breaker.py`'s thresholds. It
# only touches in-memory state and writes a history row, so a failed sweep is simply
# retried by the next tick rather than needing a retry policy of its own.
STUCK_TASK_SWEEP_INTERVAL_MINUTES = 15
STUCK_TASK_SWEEP_RETRY_ATTEMPTS = 1
STUCK_TASK_SWEEP_RETRY_DELAY_SECONDS = 0.0


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


def register_stuck_task_cleanup_job(scheduler: BackgroundScheduler) -> None:
    """Register the periodic stuck-task sweep on the shared scheduler — see
    `reap_stuck_tasks` for what it catches and why the execution budget alone isn't
    enough. Takes no `AppConfigFile`: everything it needs is a module constant above.

    Shares the `MAINTENANCE` queue with the temp-file cleanup: both are cheap, unrelated
    to any media work, and must never sit behind a bulk scan — least of all this one,
    whose entire job is to unblock queues.
    """

    def sweep() -> None:
        reaped = reap_stuck_tasks()
        if reaped:
            logger.info("stuck task sweep dropped %d abandoned task(s)", reaped)

    register_job(
        scheduler,
        sweep,
        queue=JobQueue.MAINTENANCE,
        job_id="maintenance_stuck_task_sweep",
        trigger="interval",
        minutes=STUCK_TASK_SWEEP_INTERVAL_MINUTES,
        retry_attempts=STUCK_TASK_SWEEP_RETRY_ATTEMPTS,
        retry_delay_seconds=STUCK_TASK_SWEEP_RETRY_DELAY_SECONDS,
        max_instances=1,
        coalesce=True,
    )
