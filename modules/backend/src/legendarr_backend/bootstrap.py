import logging

from apscheduler.schedulers.background import BackgroundScheduler

from legendarr_backend.media_providers.base import MediaLibraryClient
from legendarr_backend.media_providers.radarr_client import RadarrClient
from legendarr_backend.media_providers.sonarr_client import SonarrClient
from legendarr_backend.media_providers.sync_media_library import sync_media_library
from legendarr_backend.shared_kernel.config.config_file import (
    AppConfigFile,
    load_or_create_config_file,
)
from legendarr_backend.shared_kernel.config.settings import get_settings
from legendarr_backend.shared_kernel.database.engine import init_db

logger = logging.getLogger(__name__)


def _build_media_clients(
    config: AppConfigFile,
) -> tuple[MediaLibraryClient | None, MediaLibraryClient | None]:
    """Construct the concrete media library clients configured via the config file."""
    radarr = RadarrClient(config.radarr_url, config.radarr_api_key) if config.radarr_url else None
    sonarr = SonarrClient(config.sonarr_url, config.sonarr_api_key) if config.sonarr_url else None
    return radarr, sonarr


def build_scheduler() -> BackgroundScheduler:
    """Wire the periodic media sync job used by both the CLI and the web app."""
    init_db()
    config = load_or_create_config_file(get_settings())
    radarr, sonarr = _build_media_clients(config)

    def run_sync() -> None:
        result = sync_media_library(radarr, sonarr)
        logger.info("media library synced: %s", result)

    scheduler = BackgroundScheduler()
    scheduler.add_job(run_sync, "interval", minutes=config.sync_interval_minutes)
    return scheduler
