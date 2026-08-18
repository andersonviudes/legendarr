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
    # The externally-reachable address of this legendarr instance, e.g.
    # "https://legendarr.example.com" — used to build the Radarr/Sonarr webhook URL
    # shown on the Arr Services settings page. Empty means "not configured yet"; the
    # page then shows the relative webhook path with a hint instead.
    public_url: str = Field(default="")
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
    translate_retry_attempts: int = Field(default=3, ge=1)
    translate_retry_delay_seconds: float = Field(default=5.0)
    # ROADMAP.md 0.10.0 — periodic translation fan-out, same posture as
    # `subtitle_scan_interval_minutes`: config/env-only, not yet in the runtime-editable
    # Settings UI.
    translate_interval_minutes: int = Field(default=60)
    translate_max_instances: int = Field(default=1)
    translate_coalesce: bool = Field(default=True)
    default_translation_provider: str | None = Field(default=None)
    # ROADMAP.md 0.10.0 — periodic acquisition fan-out, same posture as
    # `translate_interval_minutes` above; acquisition previously took retry policy only as
    # ad-hoc function args (no scheduled job existed yet to need config-driven defaults).
    acquisition_retry_attempts: int = Field(default=3, ge=1)
    acquisition_retry_delay_seconds: float = Field(default=5.0)
    acquisition_interval_minutes: int = Field(default=60)
    acquisition_max_instances: int = Field(default=1)
    acquisition_coalesce: bool = Field(default=True)
    # Manual "sync timing" only (ROADMAP.md 0.7.0), same posture as translate_retry_attempts
    # — no interval/max_instances/coalesce fields, just the retry policy
    # `enqueue_timing_sync` needs. `ffsubsync` decodes the whole audio track, so its timeout
    # defaults higher than `embedded_subtitle_probe_timeout_seconds`.
    timing_sync_retry_attempts: int = Field(default=3, ge=1)
    timing_sync_retry_delay_seconds: float = Field(default=5.0)
    timing_sync_timeout_seconds: float = Field(default=120.0)
    # ROADMAP.md 0.9.0 — comma-separated `module.path:ClassName` entries, each imported
    # at startup by `subtitle_translation.plugins`. Env-var-only by design (not part of
    # `AppConfigFile`/`config.yaml`, not editable from the web Settings UI): this is a
    # code-import path, a different trust boundary than every other runtime value here.
    translation_plugin_packages: str = Field(default="")

    @property
    def translation_plugin_package_list(self) -> list[str]:
        return [
            entry.strip() for entry in self.translation_plugin_packages.split(",") if entry.strip()
        ]

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{self.data_dir / 'legendarr.db'}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
