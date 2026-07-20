from apscheduler.schedulers.background import BackgroundScheduler

from legendarr_backend.config.config_file import load_or_create_config_file
from legendarr_backend.config.settings import get_settings
from legendarr_backend.database.engine import init_db
from legendarr_backend.media_library.jobs import register_sync_job
from legendarr_backend.scheduling.scheduler import build_scheduler as build_bare_scheduler


def build_scheduler() -> BackgroundScheduler:
    """Wire the periodic media sync job used by both the CLI and the web app."""
    init_db()
    config = load_or_create_config_file(get_settings())

    scheduler = build_bare_scheduler()
    register_sync_job(scheduler, config)
    return scheduler
