from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for legendarr, sourced from environment variables."""

    model_config = SettingsConfigDict(env_prefix="LEGENDARR_", env_file=".env")

    data_dir: Path = Field(default=Path("./data"))
    database_url: str = Field(default="")
    radarr_url: str = Field(default="")
    radarr_api_key: str = Field(default="")
    sonarr_url: str = Field(default="")
    sonarr_api_key: str = Field(default="")
    sync_interval_minutes: int = Field(default=15)

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{self.data_dir / 'legendarr.db'}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
