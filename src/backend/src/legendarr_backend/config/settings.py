from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for legendarr, sourced from environment variables."""

    model_config = SettingsConfigDict(env_prefix="LEGENDARR_", env_file=".env")

    data_dir: Path = Field(default=Path("./data"))
    database_url: str = Field(default="")
    secret_key: str = Field(default="")
    radarr_url: str = Field(default="")
    radarr_api_key: str = Field(default="")
    sonarr_url: str = Field(default="")
    sonarr_api_key: str = Field(default="")
    sync_interval_minutes: int = Field(default=15)
    sync_retry_attempts: int = Field(default=3, ge=1)
    sync_retry_delay_seconds: float = Field(default=5.0)
    sync_max_instances: int = Field(default=1)
    sync_coalesce: bool = Field(default=True)
    scan_interval_minutes: int = Field(default=60)
    scan_retry_attempts: int = Field(default=3, ge=1)
    scan_retry_delay_seconds: float = Field(default=5.0)
    scan_max_instances: int = Field(default=1)
    scan_coalesce: bool = Field(default=True)
    history_poll_interval_minutes: int = Field(default=15)
    history_poll_retry_attempts: int = Field(default=3, ge=1)
    history_poll_retry_delay_seconds: float = Field(default=5.0)
    history_poll_max_instances: int = Field(default=1)
    history_poll_coalesce: bool = Field(default=True)
    subtitle_scan_interval_minutes: int = Field(default=60)
    subtitle_scan_retry_attempts: int = Field(default=3, ge=1)
    subtitle_scan_retry_delay_seconds: float = Field(default=5.0)
    subtitle_scan_max_instances: int = Field(default=1)
    subtitle_scan_coalesce: bool = Field(default=True)
    # ffprobe/ffmpeg subprocess timeout for embedded subtitle-track probing/extraction
    # (ROADMAP.md 0.6.0), guarding against a hung/corrupt container.
    embedded_subtitle_probe_timeout_seconds: float = Field(default=30.0)
    # Manual "translate now" only (0.10.0 unattended scheduling is a future item), so no
    # interval/max_instances/coalesce fields — just the retry policy `enqueue_translation`
    # needs.
    translate_retry_attempts: int = Field(default=3, ge=1)
    translate_retry_delay_seconds: float = Field(default=5.0)
    default_translation_provider: str | None = Field(default=None)

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{self.data_dir / 'legendarr.db'}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
