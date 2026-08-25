from apscheduler.schedulers.background import BackgroundScheduler

from legendarr_backend.config.config_file import load_or_create_config_file
from legendarr_backend.config.settings import get_settings
from legendarr_backend.database.engine import init_db
from legendarr_backend.media_library.jobs import (
    register_history_poll_job,
    register_scan_job,
    register_sync_job,
)
from legendarr_backend.scheduling.running_tasks import attach_running_task_registry
from legendarr_backend.scheduling.scheduler import build_scheduler as build_bare_scheduler
from legendarr_backend.subtitle_acquisition.jobs import register_acquisition_job
from legendarr_backend.subtitle_discovery.jobs import register_subtitle_scan_job
from legendarr_backend.subtitle_translation.jobs import register_translation_job


def build_scheduler() -> BackgroundScheduler:
    """Wire the periodic media sync job used by both the CLI and the web app."""
    init_db()
    config = load_or_create_config_file(get_settings())

    scheduler = build_bare_scheduler()
    attach_running_task_registry(scheduler)
    register_sync_job(scheduler, config)
    register_scan_job(scheduler, config)
    register_history_poll_job(scheduler, config)
    register_subtitle_scan_job(scheduler, config)
    register_translation_job(scheduler, config)
    register_acquisition_job(scheduler, config)
    return scheduler
