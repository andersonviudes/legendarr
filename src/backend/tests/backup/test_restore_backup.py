import json
import stat
from io import BytesIO
from zipfile import ZipFile

import pytest
import yaml
from legendarr_backend.backup.manage_backups import (
    CONFIG_NAME,
    MANIFEST_NAME,
    create_backup,
    list_backups,
)
from legendarr_backend.backup.restore_backup import InvalidBackupArchiveError, restore_backup
from legendarr_backend.config.config_file import AppConfigFile, update_config_file
from legendarr_backend.config.settings import Settings
from legendarr_backend.security.fernet import KEY_FILE_NAME


def _build_archive(
    *, config: dict | None = None, manifest: dict | None = None, include_key: bool = False
) -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        if manifest is not None:
            archive.writestr(MANIFEST_NAME, json.dumps(manifest))
        if config is not None:
            archive.writestr(CONFIG_NAME, yaml.safe_dump(config))
        if include_key:
            archive.writestr(KEY_FILE_NAME, "not-a-real-key")
    return buffer.getvalue()


def _valid_manifest(secret_key_included: bool = False) -> dict:
    return {"created_at": "2026-08-28T00:00:00+00:00", "secret_key_included": secret_key_included}


def test_restore_backup_overwrites_config_from_the_archive(tmp_path):
    settings = Settings(data_dir=tmp_path, database_url="")
    update_config_file(settings, {"public_url": "https://first.example.com"})
    backup = create_backup(settings)
    archive_bytes = (tmp_path / "backups" / backup.filename).read_bytes()
    update_config_file(settings, {"public_url": "https://second.example.com"})

    result = restore_backup(settings, archive_bytes)

    assert "restart" in result.message.lower()
    stored = yaml.safe_load((tmp_path / "config.yaml").read_text())
    assert stored["public_url"] == "https://first.example.com"


def test_restore_backup_takes_a_safety_snapshot_first(tmp_path):
    settings = Settings(data_dir=tmp_path, database_url="")
    backup = create_backup(settings)
    archive_bytes = (tmp_path / "backups" / backup.filename).read_bytes()

    restore_backup(settings, archive_bytes)

    # The original backup plus the pre-restore safety snapshot.
    assert len(list_backups(settings)) == 2


def test_restore_backup_writes_bundled_secret_key_with_owner_only_permissions(tmp_path):
    settings = Settings(data_dir=tmp_path, database_url="")
    config = AppConfigFile().model_dump()
    archive_bytes = _build_archive(
        config=config, manifest=_valid_manifest(secret_key_included=True), include_key=True
    )

    restore_backup(settings, archive_bytes)

    key_path = tmp_path / KEY_FILE_NAME
    assert key_path.read_text() == "not-a-real-key"
    assert stat.S_IMODE(key_path.stat().st_mode) == 0o600


def test_restore_backup_rejects_non_zip_content(tmp_path):
    settings = Settings(data_dir=tmp_path, database_url="")

    with pytest.raises(InvalidBackupArchiveError):
        restore_backup(settings, b"not a zip file")


def test_restore_backup_rejects_archive_missing_config(tmp_path):
    settings = Settings(data_dir=tmp_path, database_url="")
    archive_bytes = _build_archive(manifest=_valid_manifest())

    with pytest.raises(InvalidBackupArchiveError):
        restore_backup(settings, archive_bytes)


def test_restore_backup_rejects_archive_missing_manifest(tmp_path):
    settings = Settings(data_dir=tmp_path, database_url="")
    archive_bytes = _build_archive(config=AppConfigFile().model_dump())

    with pytest.raises(InvalidBackupArchiveError):
        restore_backup(settings, archive_bytes)


def test_restore_backup_rejects_invalid_config_yaml(tmp_path):
    settings = Settings(data_dir=tmp_path, database_url="")
    archive_bytes = _build_archive(config={"sync_retry_attempts": 0}, manifest=_valid_manifest())

    with pytest.raises(InvalidBackupArchiveError):
        restore_backup(settings, archive_bytes)


def test_restore_backup_rejects_manifest_claiming_a_key_not_in_the_archive(tmp_path):
    settings = Settings(data_dir=tmp_path, database_url="")
    archive_bytes = _build_archive(
        config=AppConfigFile().model_dump(),
        manifest=_valid_manifest(secret_key_included=True),
        include_key=False,
    )

    with pytest.raises(InvalidBackupArchiveError):
        restore_backup(settings, archive_bytes)


def test_restore_backup_leaves_config_untouched_on_validation_failure(tmp_path):
    settings = Settings(data_dir=tmp_path, database_url="")
    update_config_file(settings, {"public_url": "https://untouched.example.com"})
    before = (tmp_path / "config.yaml").read_text()

    with pytest.raises(InvalidBackupArchiveError):
        restore_backup(settings, b"not a zip file")

    assert (tmp_path / "config.yaml").read_text() == before
