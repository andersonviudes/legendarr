"""Create/list/delete `config.yaml` (+ Fernet key) backup archives (ROADMAP.md 0.22.0).

Deliberately doesn't touch the SQLite database — this only snapshots `data_dir/config.yaml`
and, when it's a file rather than `LEGENDARR_SECRET_KEY`, `data_dir/.secret_key`. Both are
already at-rest-encrypted/plaintext-key-material as they sit on disk, so a backup is a
straight file copy into a zip, no re-encryption involved.
"""

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from zipfile import ZipFile

from legendarr_backend.backup.schemas import BackupRead
from legendarr_backend.config.config_file import load_or_create_config_file
from legendarr_backend.config.settings import Settings
from legendarr_backend.security.fernet import KEY_FILE_NAME

# Microseconds, not just seconds, so two backups triggered back-to-back (e.g. a
# doubled-click "Create backup", or restore's own pre-restore safety snapshot landing in
# the same second as a manual one) never collide on the same filename.
_FILENAME_PATTERN = re.compile(r"^legendarr-backup-\d{8}T\d{12}Z\.zip$")
# Shared with `restore_backup.py`, which reads an uploaded archive back apart.
MANIFEST_NAME = "manifest.json"
CONFIG_NAME = "config.yaml"


def is_valid_backup_filename(filename: str) -> bool:
    """Whether `filename` matches the archive naming scheme — checked before any
    filesystem access in every create/list/delete/download/restore entry point, as a
    path-traversal guard against something like `../../etc/passwd`."""
    return bool(_FILENAME_PATTERN.fullmatch(filename))


def backups_dir(settings: Settings) -> Path:
    path = settings.data_dir / "backups"
    path.mkdir(parents=True, exist_ok=True)
    return path


def create_backup(settings: Settings) -> BackupRead:
    """Snapshot the current `config.yaml` (+ `.secret_key`, if file-based) into a new
    zip archive, then prune the oldest archives beyond `backup_retention_count`."""
    load_or_create_config_file(settings)  # ensure config.yaml exists before archiving it
    config_path = settings.data_dir / "config.yaml"
    key_path = settings.data_dir / KEY_FILE_NAME
    secret_key_included = not settings.secret_key and key_path.exists()

    created_at = datetime.now(UTC)
    filename = f"legendarr-backup-{created_at:%Y%m%dT%H%M%S%fZ}.zip"
    path = backups_dir(settings) / filename
    manifest = {
        "created_at": created_at.isoformat(),
        "secret_key_included": secret_key_included,
    }
    with ZipFile(path, "w") as archive:
        archive.writestr(MANIFEST_NAME, json.dumps(manifest))
        archive.write(config_path, CONFIG_NAME)
        if secret_key_included:
            archive.write(key_path, KEY_FILE_NAME)

    _prune_old_backups(settings)
    return BackupRead(
        filename=filename,
        created_at=created_at,
        size_bytes=path.stat().st_size,
        secret_key_included=secret_key_included,
    )


def list_backups(settings: Settings) -> list[BackupRead]:
    """Every archive in `data_dir/backups/`, newest first. A file that doesn't match the
    naming scheme or whose manifest can't be read is skipped rather than failing the
    whole listing."""
    backups = []
    for path in backups_dir(settings).iterdir():
        if not is_valid_backup_filename(path.name):
            continue
        backup = _read_backup(path)
        if backup is not None:
            backups.append(backup)
    backups.sort(key=lambda backup: backup.created_at, reverse=True)
    return backups


def delete_backup(settings: Settings, filename: str) -> bool:
    """Delete one archive. Returns whether it existed — same shape as
    `arr_services.delete_arr_service`/`language_profiles.delete_language_profile`, so the
    router can 404 the same way."""
    if not is_valid_backup_filename(filename):
        return False
    path = backups_dir(settings) / filename
    if not path.is_file():
        return False
    path.unlink()
    return True


def _read_backup(path: Path) -> BackupRead | None:
    try:
        with ZipFile(path) as archive:
            manifest = json.loads(archive.read(MANIFEST_NAME))
        return BackupRead(
            filename=path.name,
            created_at=datetime.fromisoformat(manifest["created_at"]),
            size_bytes=path.stat().st_size,
            secret_key_included=manifest["secret_key_included"],
        )
    except (OSError, KeyError, ValueError):
        return None


def _prune_old_backups(settings: Settings) -> None:
    """Delete the oldest archives beyond `backup_retention_count` — filenames sort
    lexicographically in the same order as `created_at` since the timestamp format is
    fixed-width, so no need to open every zip just to prune."""
    filenames = sorted(
        (path for path in backups_dir(settings).iterdir() if is_valid_backup_filename(path.name)),
        reverse=True,
    )
    for path in filenames[settings.backup_retention_count :]:
        path.unlink()
