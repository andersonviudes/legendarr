from cryptography.fernet import Fernet, InvalidToken

ENCRYPTED_PREFIX = "enc:v1:"


class SecretDecryptionError(Exception):
    """A value marked as encrypted couldn't be decrypted — almost always a lost or
    rotated secret key."""


def is_encrypted(value: str) -> bool:
    return value.startswith(ENCRYPTED_PREFIX)


def encrypt_secret(plain: str, fernet: Fernet) -> str:
    """Encrypt a secret for storage. Idempotent: already-encrypted input passes through,
    and empty values stay empty."""
    if not plain or plain.startswith(ENCRYPTED_PREFIX):
        return plain
    return ENCRYPTED_PREFIX + fernet.encrypt(plain.encode()).decode()


def decrypt_secret(value: str, fernet: Fernet) -> str:
    """Decrypt a stored secret. Values without the encryption prefix are legacy plaintext
    and returned as-is, so pre-encryption installs keep working until their next save."""
    if not value or not value.startswith(ENCRYPTED_PREFIX):
        return value
    token = value[len(ENCRYPTED_PREFIX) :].encode()
    try:
        return fernet.decrypt(token).decode()
    except InvalidToken as exc:
        raise SecretDecryptionError(
            "A stored secret could not be decrypted — the secret key was likely lost or "
            "changed. Restore the original key (LEGENDARR_SECRET_KEY or the key file in "
            "the data directory) and re-enter the affected API keys."
        ) from exc
