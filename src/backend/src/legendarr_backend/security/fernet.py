import logging
import os
from functools import lru_cache

from cryptography.fernet import Fernet

from legendarr_backend.config.settings import Settings, get_settings

logger = logging.getLogger(__name__)

KEY_FILE_NAME = ".secret_key"


def resolve_fernet(settings: Settings) -> Fernet:
    """Build the Fernet cipher from the configured key, generating one if needed.

    `LEGENDARR_SECRET_KEY` takes precedence; otherwise a key is read from (or generated
    into) `<data_dir>/.secret_key`, so encrypted data survives restarts with zero setup.
    """
    if settings.secret_key:
        return Fernet(_validate_key(settings.secret_key.encode()))
    return Fernet(_read_or_create_key_file(settings))


def _validate_key(key: bytes) -> bytes:
    try:
        Fernet(key)
    except ValueError as exc:
        raise ValueError(
            "Secret key is not a valid Fernet key — generate one with `python -c "
            '"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`'
        ) from exc
    return key


def _read_or_create_key_file(settings: Settings) -> bytes:
    path = settings.data_dir / KEY_FILE_NAME
    if path.exists():
        return _validate_key(path.read_bytes().strip())
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    key = Fernet.generate_key()
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        # Another process won the race between the existence check and creation.
        return _validate_key(path.read_bytes().strip())
    with os.fdopen(fd, "wb") as file:
        file.write(key)
    logger.info("Generated new secret key file at %s", path)
    return key


@lru_cache
def get_fernet() -> Fernet:
    """Process-wide cipher built from ambient settings — for call sites that can't inject."""
    return resolve_fernet(get_settings())
