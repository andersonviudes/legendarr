import hashlib
import hmac
import secrets

_HASH_PREFIX = "pbkdf2_sha256"
_ITERATIONS = 600_000
_SALT_BYTES = 16


def hash_password(plain: str) -> str:
    """Hash a password for storage: `pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>` —
    versioned prefix like `security/secrets.py`'s `enc:v1:`, so the iteration count (or
    algorithm) can change later without breaking existing hashes."""
    salt = secrets.token_hex(_SALT_BYTES)
    digest = _derive(plain, salt, _ITERATIONS)
    return f"{_HASH_PREFIX}${_ITERATIONS}${salt}${digest}"


def verify_password(plain: str, stored_hash: str) -> bool:
    """Check `plain` against a hash produced by `hash_password`. Constant-time compare
    on the digest so a mismatch can't be timed to leak how many leading bytes matched."""
    try:
        prefix, iterations, salt, digest = stored_hash.split("$")
    except ValueError:
        return False
    if prefix != _HASH_PREFIX:
        return False
    return hmac.compare_digest(_derive(plain, salt, int(iterations)), digest)


def generate_api_key() -> str:
    """A fresh bearer token for non-interactive `/api` access (ROADMAP.md 0.16.0)."""
    return secrets.token_urlsafe(32)


def _derive(plain: str, salt: str, iterations: int) -> str:
    return hashlib.pbkdf2_hmac("sha256", plain.encode(), salt.encode(), iterations).hex()
