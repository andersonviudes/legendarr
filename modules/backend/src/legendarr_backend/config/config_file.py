from pathlib import Path

import yaml
from cryptography.fernet import Fernet
from pydantic import BaseModel, Field

from legendarr_backend.config.settings import Settings
from legendarr_backend.security.fernet import resolve_fernet
from legendarr_backend.security.secrets import decrypt_secret, encrypt_secret, is_encrypted

_SECRET_FIELDS = ("radarr_api_key", "sonarr_api_key")


class AppConfigFile(BaseModel):
    """Runtime configuration persisted to disk alongside the database.

    Unlike `Settings` (bootstrap config sourced from env vars), this file is read
    before the database is created/opened, and is the file the Settings feature
    will read and rewrite once it exists.

    In-memory values are plaintext; the `*_api_key` fields are encrypted on disk.
    """

    database_url: str = ""
    radarr_url: str = ""
    radarr_api_key: str = ""
    sonarr_url: str = ""
    sonarr_api_key: str = ""
    sync_interval_minutes: int = 15
    sync_retry_attempts: int = Field(default=3, ge=1)
    sync_retry_delay_seconds: float = 5.0
    sync_max_instances: int = 1
    sync_coalesce: bool = True
    scan_interval_minutes: int = 60
    scan_retry_attempts: int = Field(default=3, ge=1)
    scan_retry_delay_seconds: float = 5.0
    scan_max_instances: int = 1
    scan_coalesce: bool = True
    history_poll_interval_minutes: int = 15
    history_poll_retry_attempts: int = Field(default=3, ge=1)
    history_poll_retry_delay_seconds: float = 5.0
    history_poll_max_instances: int = 1
    history_poll_coalesce: bool = True
    subtitle_scan_interval_minutes: int = 60
    subtitle_scan_retry_attempts: int = Field(default=3, ge=1)
    subtitle_scan_retry_delay_seconds: float = 5.0
    subtitle_scan_max_instances: int = 1
    subtitle_scan_coalesce: bool = True
    translate_retry_attempts: int = Field(default=3, ge=1)
    translate_retry_delay_seconds: float = 5.0


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
        "sync_retry_attempts": settings.sync_retry_attempts,
        "sync_retry_delay_seconds": settings.sync_retry_delay_seconds,
        "sync_max_instances": settings.sync_max_instances,
        "sync_coalesce": settings.sync_coalesce,
        "scan_interval_minutes": settings.scan_interval_minutes,
        "scan_retry_attempts": settings.scan_retry_attempts,
        "scan_retry_delay_seconds": settings.scan_retry_delay_seconds,
        "scan_max_instances": settings.scan_max_instances,
        "scan_coalesce": settings.scan_coalesce,
        "history_poll_interval_minutes": settings.history_poll_interval_minutes,
        "history_poll_retry_attempts": settings.history_poll_retry_attempts,
        "history_poll_retry_delay_seconds": settings.history_poll_retry_delay_seconds,
        "history_poll_max_instances": settings.history_poll_max_instances,
        "history_poll_coalesce": settings.history_poll_coalesce,
        "subtitle_scan_interval_minutes": settings.subtitle_scan_interval_minutes,
        "subtitle_scan_retry_attempts": settings.subtitle_scan_retry_attempts,
        "subtitle_scan_retry_delay_seconds": settings.subtitle_scan_retry_delay_seconds,
        "subtitle_scan_max_instances": settings.subtitle_scan_max_instances,
        "subtitle_scan_coalesce": settings.subtitle_scan_coalesce,
        "translate_retry_attempts": settings.translate_retry_attempts,
        "translate_retry_delay_seconds": settings.translate_retry_delay_seconds,
    }
    merged = {**defaults, **data}
    config = AppConfigFile.model_validate(merged)

    fernet = resolve_fernet(settings)
    if merged != data or _has_plaintext_secrets(merged):
        _write_config_file(path, config, fernet)

    # Callers always get plaintext, regardless of what's stored on disk.
    return config.model_copy(
        update={field: decrypt_secret(merged[field], fernet) for field in _SECRET_FIELDS}
    )


def update_config_file(settings: Settings, updates: dict) -> AppConfigFile:
    """Apply `updates` to the persisted runtime config and rewrite `config.yaml`.

    Loads the current file (so untouched fields — including the encrypted secrets —
    round-trip), validates the merged result through `AppConfigFile`, and rewrites the
    whole file. Returns the updated config with plaintext secrets, like the loader.
    """
    config = load_or_create_config_file(settings)
    updated = config.model_copy(update=updates)
    _write_config_file(settings.data_dir / "config.yaml", updated, resolve_fernet(settings))
    return updated


def _has_plaintext_secrets(data: dict) -> bool:
    """Detect legacy plaintext secrets so they get re-encrypted even when nothing else
    in the file changed."""
    return any(data[field] and not is_encrypted(data[field]) for field in _SECRET_FIELDS)


def _write_config_file(path: Path, config: AppConfigFile, fernet: Fernet) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    stored = config.model_dump()
    for field in _SECRET_FIELDS:
        stored[field] = encrypt_secret(stored[field], fernet)
    path.write_text(yaml.safe_dump(stored))
