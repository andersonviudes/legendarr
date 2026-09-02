from apscheduler.schedulers.background import BackgroundScheduler

from legendarr_backend.config.config_file import load_or_create_config_file
from legendarr_backend.config.settings import get_settings
from legendarr_backend.database.engine import init_db
from legendarr_backend.maintenance.jobs import register_temp_file_cleanup_job
from legendarr_backend.media_library.jobs import (
    register_history_poll_job,
    register_scan_job,
    register_sync_job,
)
from legendarr_backend.media_metadata.jobs import (
    register_metadata_refresh_job,
    register_poster_cache_cleanup_job,
)
from legendarr_backend.scheduling.queues import JobQueue
from legendarr_backend.scheduling.running_tasks import attach_running_task_registry
from legendarr_backend.scheduling.scheduled_retry import attach_scheduled_retry
from legendarr_backend.scheduling.scheduler import build_scheduler as build_bare_scheduler
from legendarr_backend.subtitle_acquisition.jobs import register_acquisition_job
from legendarr_backend.subtitle_acquisition.upgrade_jobs import register_subtitle_upgrade_job
from legendarr_backend.subtitle_discovery.jobs import register_subtitle_scan_job
from legendarr_backend.subtitle_translation.jobs import register_translation_job
from legendarr_backend.system.job_history import attach_job_history_recorder


def build_scheduler() -> BackgroundScheduler:
    """Wire the periodic media sync job used by both the CLI and the web app."""
    init_db()
    config = load_or_create_config_file(get_settings())

    queue_workers = {
        JobQueue.SYNC: config.sync_queue_workers,
        JobQueue.SCAN: config.scan_queue_workers,
        JobQueue.SCAN_BULK: config.scan_bulk_queue_workers,
        JobQueue.TRANSLATE: config.translate_queue_workers,
        JobQueue.TRANSLATE_BULK: config.translate_bulk_queue_workers,
        JobQueue.ACQUIRE: config.acquire_queue_workers,
        JobQueue.ACQUIRE_BULK: config.acquire_bulk_queue_workers,
        JobQueue.TIMING_SYNC: config.timing_sync_queue_workers,
        JobQueue.METADATA_BULK: config.metadata_bulk_queue_workers,
        JobQueue.MAINTENANCE: config.maintenance_queue_workers,
        JobQueue.UPGRADE_BULK: config.upgrade_bulk_queue_workers,
    }
    scheduler = build_bare_scheduler(queue_workers)
    attach_running_task_registry(scheduler, queue_workers)
    attach_job_history_recorder(scheduler)
    attach_scheduled_retry(scheduler)
    register_sync_job(scheduler, config)
    register_scan_job(scheduler, config)
    register_history_poll_job(scheduler, config)
    register_subtitle_scan_job(scheduler, config)
    register_translation_job(scheduler, config)
    register_acquisition_job(scheduler, config)
    register_subtitle_upgrade_job(scheduler, config)
    register_metadata_refresh_job(scheduler, config)
    register_poster_cache_cleanup_job(scheduler, config)
    register_temp_file_cleanup_job(scheduler, config)
    return scheduler
