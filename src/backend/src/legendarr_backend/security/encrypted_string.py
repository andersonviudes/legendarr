from sqlalchemy import String
from sqlalchemy.types import TypeDecorator

from legendarr_backend.security.fernet import get_fernet
from legendarr_backend.security.secrets import decrypt_secret, encrypt_secret


class EncryptedString(TypeDecorator):
    """String column transparently encrypted at rest (Fernet, `enc:v1:` prefix).

    Reads tolerate legacy plaintext rows (no prefix), which are re-encrypted on their
    next update — so no data migration is needed when this is applied to a column that
    already holds plaintext.
    """

    impl = String
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        return encrypt_secret(value, get_fernet())

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        return decrypt_secret(value, get_fernet())
