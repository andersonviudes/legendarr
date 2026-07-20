import os
import stat

import pytest
from cryptography.fernet import Fernet
from legendarr_backend.config.settings import Settings
from legendarr_backend.security.fernet import KEY_FILE_NAME, resolve_fernet


def test_env_var_key_takes_precedence_and_creates_no_file(tmp_path):
    key = Fernet.generate_key().decode()
    settings = Settings(data_dir=tmp_path, database_url="", secret_key=key)

    fernet = resolve_fernet(settings)

    assert fernet.decrypt(fernet.encrypt(b"probe")) == b"probe"
    assert not (tmp_path / KEY_FILE_NAME).exists()


def test_invalid_env_var_key_raises(tmp_path):
    settings = Settings(data_dir=tmp_path, database_url="", secret_key="not-a-fernet-key")

    with pytest.raises(ValueError, match="not a valid Fernet key"):
        resolve_fernet(settings)


def test_generates_key_file_with_owner_only_permissions(tmp_path):
    settings = Settings(data_dir=tmp_path, database_url="")

    resolve_fernet(settings)

    key_path = tmp_path / KEY_FILE_NAME
    assert key_path.exists()
    mode = stat.S_IMODE(os.stat(key_path).st_mode)
    assert mode == 0o600


def test_reuses_existing_key_file_across_calls(tmp_path):
    settings = Settings(data_dir=tmp_path, database_url="")

    first = resolve_fernet(settings)
    second = resolve_fernet(settings)

    token = first.encrypt(b"probe")
    assert second.decrypt(token) == b"probe"


def test_invalid_key_file_content_raises(tmp_path):
    (tmp_path / KEY_FILE_NAME).write_text("not-a-fernet-key")
    settings = Settings(data_dir=tmp_path, database_url="")

    with pytest.raises(ValueError, match="not a valid Fernet key"):
        resolve_fernet(settings)
