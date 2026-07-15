import logging

from apscheduler.schedulers.background import BackgroundScheduler

from legendarr_backend.media_providers.radarr_client import RadarrClient
from legendarr_backend.media_providers.sonarr_client import SonarrClient
from legendarr_backend.media_providers.sync_media_library import sync_media_library
from legendarr_backend.shared_kernel.config import get_settings
from legendarr_backend.shared_kernel.database import init_db

logger = logging.getLogger(__name__)


def build_scheduler() -> BackgroundScheduler:
    """Wire the periodic media sync job used by both the CLI and the web app."""
    settings = get_settings()
    init_db()

    radarr = (
        RadarrClient(settings.radarr_url, settings.radarr_api_key) if settings.radarr_url else None
    )
    sonarr = (
        SonarrClient(settings.sonarr_url, settings.sonarr_api_key) if settings.sonarr_url else None
    )

    def run_sync() -> None:
        result = sync_media_library(radarr, sonarr)
        logger.info("media library synced: %s", result)

    scheduler = BackgroundScheduler()
    scheduler.add_job(run_sync, "interval", minutes=settings.sync_interval_minutes)
    return scheduler
