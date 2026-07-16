import yaml
from pydantic import BaseModel

from legendarr_backend.shared_kernel.config.settings import Settings


class AppConfigFile(BaseModel):
    """Runtime configuration persisted to disk alongside the database.

    Unlike `Settings` (bootstrap config sourced from env vars), this file is read
    before the database is created/opened, and is the file the Settings feature
    will read and rewrite once it exists.
    """

    database_url: str = ""
    radarr_url: str = ""
    radarr_api_key: str = ""
    sonarr_url: str = ""
    sonarr_api_key: str = ""
    sync_interval_minutes: int = 15


def load_or_create_config_file(settings: Settings) -> AppConfigFile:
    path = settings.data_dir / "config.yaml"
    data = yaml.safe_load(path.read_text()) or {} if path.exists() else {}

    defaults = {
        "database_url": settings.resolved_database_url,
        "radarr_url": settings.radarr_url,
        "radarr_api_key": settings.radarr_api_key,
        "sonarr_url": settings.sonarr_url,
        "sonarr_api_key": settings.sonarr_api_key,
        "sync_interval_minutes": settings.sync_interval_minutes,
    }
    merged = {**defaults, **data}
    config = AppConfigFile.model_validate(merged)

    if merged != data:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(config.model_dump()))

    return config
