from apscheduler.schedulers.background import BackgroundScheduler

from legendarr_backend.arr_clients.base import MediaLibraryClient
from legendarr_backend.arr_clients.radarr_client import RadarrClient
from legendarr_backend.arr_clients.sonarr_client import SonarrClient
from legendarr_backend.config.config_file import (
    AppConfigFile,
    load_or_create_config_file,
)
from legendarr_backend.config.settings import get_settings
from legendarr_backend.database.engine import init_db
from legendarr_backend.media_library.jobs import register_sync_job
from legendarr_backend.scheduling.scheduler import build_scheduler as build_bare_scheduler


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

    scheduler = build_bare_scheduler()
    register_sync_job(scheduler, config, radarr, sonarr)
    return scheduler
