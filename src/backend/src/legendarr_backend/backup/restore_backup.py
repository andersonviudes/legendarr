"""Restore `config.yaml` (+ Fernet key) from a previously-created backup archive
(ROADMAP.md 0.22.0). See `manage_backups.py` for what the archive does and doesn't cover.
"""

import json
import os
from io import BytesIO
from zipfile import BadZipFile, ZipFile

import yaml

from legendarr_backend.backup.manage_backups import CONFIG_NAME, MANIFEST_NAME, create_backup
from legendarr_backend.backup.schemas import RestoreResult
from legendarr_backend.config.config_file import AppConfigFile
from legendarr_backend.config.settings import Settings
from legendarr_backend.security.fernet import KEY_FILE_NAME


class InvalidBackupArchiveError(Exception):
    """`content` isn't a legendarr backup archive — missing/unreadable manifest,
    missing `config.yaml`, a `config.yaml` that fails validation, or a manifest claiming
    a bundled Fernet key that isn't actually in the archive."""


def restore_backup(settings: Settings, content: bytes) -> RestoreResult:
    """Validate `content` as a backup archive, snapshot the *current* config as a safety
    net, then overwrite `config.yaml` (and `.secret_key`, if the archive bundled one).

    Never hot-swaps the running process's cached `Settings`/Fernet cipher/scheduler —
    the caller must restart legendarr for the restored config to take effect.
    """
    config_bytes, key_bytes = _read_archive(content)

    create_backup(settings)  # safety snapshot of the config being overwritten

    (settings.data_dir / CONFIG_NAME).write_bytes(config_bytes)
    if key_bytes is not None:
        key_path = settings.data_dir / KEY_FILE_NAME
        key_path.write_bytes(key_bytes)
        os.chmod(key_path, 0o600)

    return RestoreResult(
        message=(
            "Restore complete. Restart legendarr for the restored configuration to take effect."
        )
    )


def _read_archive(content: bytes) -> tuple[bytes, bytes | None]:
    try:
        archive = ZipFile(BytesIO(content))
    except BadZipFile as exc:
        raise InvalidBackupArchiveError("Not a valid backup archive.") from exc

    names = set(archive.namelist())
    if MANIFEST_NAME not in names or CONFIG_NAME not in names:
        raise InvalidBackupArchiveError("Archive is missing config.yaml or manifest.json.")

    try:
        manifest = json.loads(archive.read(MANIFEST_NAME))
        secret_key_included = bool(manifest["secret_key_included"])
    except (json.JSONDecodeError, KeyError) as exc:
        raise InvalidBackupArchiveError("Archive's manifest.json is invalid.") from exc

    config_bytes = archive.read(CONFIG_NAME)
    try:
        AppConfigFile.model_validate(yaml.safe_load(config_bytes) or {})
    except (yaml.YAMLError, ValueError) as exc:
        raise InvalidBackupArchiveError("Archive's config.yaml is invalid.") from exc

    key_bytes = None
    if secret_key_included:
        if KEY_FILE_NAME not in names:
            raise InvalidBackupArchiveError(
                "Archive's manifest claims a bundled secret key that isn't in the archive."
            )
        key_bytes = archive.read(KEY_FILE_NAME)

    return config_bytes, key_bytes
