import yaml
from pydantic import BaseModel

from legendarr_backend.shared_kernel.config import Settings


class AppConfigFile(BaseModel):
    """Runtime configuration persisted to disk alongside the database.

    Unlike `Settings` (bootstrap config sourced from env vars), this file is read
    before the database is created/opened, and is the file the Settings feature
    will read and rewrite once it exists.
    """

    database_url: str


def load_or_create_config_file(settings: Settings) -> AppConfigFile:
    path = settings.data_dir / "config.yaml"
    if path.exists():
        data = yaml.safe_load(path.read_text()) or {}
        return AppConfigFile.model_validate(data)

    config = AppConfigFile(database_url=settings.resolved_database_url)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(config.model_dump()))
    return config
