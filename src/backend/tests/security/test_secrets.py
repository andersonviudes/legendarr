import pytest
from cryptography.fernet import Fernet
from legendarr_backend.security.secrets import (
    ENCRYPTED_PREFIX,
    SecretDecryptionError,
    decrypt_secret,
    encrypt_secret,
)


@pytest.fixture
def fernet():
    return Fernet(Fernet.generate_key())


def test_encrypt_then_decrypt_round_trips(fernet):
    encrypted = encrypt_secret("my-api-key", fernet)

    assert encrypted.startswith(ENCRYPTED_PREFIX)
    assert "my-api-key" not in encrypted
    assert decrypt_secret(encrypted, fernet) == "my-api-key"


def test_encrypt_is_idempotent(fernet):
    encrypted = encrypt_secret("my-api-key", fernet)

    assert encrypt_secret(encrypted, fernet) == encrypted


def test_encrypt_leaves_empty_values_alone(fernet):
    assert encrypt_secret("", fernet) == ""


def test_decrypt_passes_legacy_plaintext_through(fernet):
    assert decrypt_secret("plain-legacy-key", fernet) == "plain-legacy-key"


def test_decrypt_leaves_empty_values_alone(fernet):
    assert decrypt_secret("", fernet) == ""


def test_decrypt_rejects_ciphertext_with_the_wrong_key(fernet):
    encrypted = encrypt_secret("my-api-key", Fernet(Fernet.generate_key()))

    with pytest.raises(SecretDecryptionError):
        decrypt_secret(encrypted, fernet)


def test_decrypt_rejects_corrupt_ciphertext(fernet):
    with pytest.raises(SecretDecryptionError):
        decrypt_secret(f"{ENCRYPTED_PREFIX}not-a-real-token", fernet)
