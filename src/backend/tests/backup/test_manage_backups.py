import json
from zipfile import ZipFile

from cryptography.fernet import Fernet
from legendarr_backend.backup.manage_backups import (
    CONFIG_NAME,
    MANIFEST_NAME,
    create_backup,
    delete_backup,
    is_valid_backup_filename,
    list_backups,
)
from legendarr_backend.config.settings import Settings
from legendarr_backend.security.fernet import KEY_FILE_NAME


def test_create_backup_bundles_config_and_secret_key_by_default(tmp_path):
    settings = Settings(data_dir=tmp_path, database_url="")

    backup = create_backup(settings)

    assert backup.secret_key_included is True
    path = tmp_path / "backups" / backup.filename
    assert path.exists()
    with ZipFile(path) as archive:
        assert set(archive.namelist()) == {MANIFEST_NAME, CONFIG_NAME, KEY_FILE_NAME}
        manifest = json.loads(archive.read(MANIFEST_NAME))
        assert manifest["secret_key_included"] is True
        assert archive.read(CONFIG_NAME) == (tmp_path / "config.yaml").read_bytes()
        assert archive.read(KEY_FILE_NAME) == (tmp_path / KEY_FILE_NAME).read_bytes()


def test_create_backup_excludes_secret_key_when_env_var_driven(tmp_path):
    key = Fernet.generate_key().decode()
    settings = Settings(data_dir=tmp_path, database_url="", secret_key=key)

    backup = create_backup(settings)

    assert backup.secret_key_included is False
    with ZipFile(tmp_path / "backups" / backup.filename) as archive:
        assert set(archive.namelist()) == {MANIFEST_NAME, CONFIG_NAME}


def test_list_backups_returns_newest_first(tmp_path):
    settings = Settings(data_dir=tmp_path, database_url="")
    first = create_backup(settings)
    second = create_backup(settings)

    backups = list_backups(settings)

    assert [backup.filename for backup in backups] == [second.filename, first.filename]


def test_list_backups_skips_files_that_dont_match_the_naming_scheme(tmp_path):
    settings = Settings(data_dir=tmp_path, database_url="")
    create_backup(settings)
    (tmp_path / "backups").mkdir(parents=True, exist_ok=True)
    (tmp_path / "backups" / "not-a-backup.zip").write_bytes(b"garbage")

    backups = list_backups(settings)

    assert len(backups) == 1


def test_delete_backup_removes_the_file(tmp_path):
    settings = Settings(data_dir=tmp_path, database_url="")
    backup = create_backup(settings)

    assert delete_backup(settings, backup.filename) is True
    assert not (tmp_path / "backups" / backup.filename).exists()


def test_delete_backup_returns_false_for_missing_or_invalid_filename(tmp_path):
    settings = Settings(data_dir=tmp_path, database_url="")

    assert delete_backup(settings, "legendarr-backup-20260101T000000000000Z.zip") is False
    assert delete_backup(settings, "../../etc/passwd") is False


def test_is_valid_backup_filename_rejects_path_traversal():
    assert is_valid_backup_filename("../../etc/passwd") is False
    assert is_valid_backup_filename("legendarr-backup-20260101T000000000000Z.zip") is True


def test_retention_prunes_oldest_backups_beyond_the_configured_count(tmp_path):
    settings = Settings(data_dir=tmp_path, database_url="", backup_retention_count=2)
    first = create_backup(settings)
    second = create_backup(settings)
    third = create_backup(settings)

    remaining = {backup.filename for backup in list_backups(settings)}

    assert remaining == {second.filename, third.filename}
    assert not (tmp_path / "backups" / first.filename).exists()
