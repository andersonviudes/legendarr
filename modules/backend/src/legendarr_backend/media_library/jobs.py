import logging

from apscheduler.schedulers.background import BackgroundScheduler

from legendarr_backend.arr_clients.base import MediaLibraryClient
from legendarr_backend.config.config_file import AppConfigFile
from legendarr_backend.media_library.sync_media_library import sync_media_library
from legendarr_backend.scheduling.queues import JobQueue
from legendarr_backend.scheduling.scheduler import register_job

logger = logging.getLogger(__name__)


def register_sync_job(
    scheduler: BackgroundScheduler,
    config: AppConfigFile,
    radarr: MediaLibraryClient | None,
    sonarr: MediaLibraryClient | None,
) -> None:
    """Register the periodic media library sync job on the shared scheduler."""

    def run_sync() -> None:
        result = sync_media_library(radarr, sonarr)
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
