import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

from sqlmodel import Session, col, select

from legendarr_backend.authentication.models import AuthSession
from legendarr_backend.authentication.passwords import (
    generate_api_key,
    hash_password,
    verify_password,
)
from legendarr_backend.authentication.schemas import AuthSettingsRead, AuthSettingsUpdate
from legendarr_backend.config.config_file import load_or_create_config_file, update_config_file
from legendarr_backend.config.settings import Settings

# ROADMAP.md 0.16.0 — sliding session lifetime, not exposed as a Settings field.
SESSION_TTL = timedelta(days=30)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _utcnow() -> datetime:
    """Naive UTC `now` — SQLite drops tzinfo on round trip, so a value read back from
    `AuthSession` is always naive; comparing/storing naive-but-UTC throughout avoids ever
    mixing aware and naive datetimes."""
    return datetime.now(UTC).replace(tzinfo=None)


def verify_login(settings: Settings, username: str, password: str) -> bool:
    """Check credentials against the single stored admin account. A missing/empty
    stored hash never matches, so an unconfigured account can't be logged into."""
    config = load_or_create_config_file(settings)
    if not config.auth_username or not config.auth_password_hash:
        return False
    return username == config.auth_username and verify_password(password, config.auth_password_hash)


def create_session(
    db_session: Session, *, ip_address: str, user_agent: str
) -> tuple[AuthSession, str]:
    """Start a new session, returning the row and the raw token — the only place the raw
    token ever exists; only its hash is persisted (`AuthSession.token_hash`)."""
    token = secrets.token_urlsafe(32)
    now = _utcnow()
    auth_session = AuthSession(
        token_hash=_hash_token(token),
        created_at=now,
        last_seen_at=now,
        expires_at=now + SESSION_TTL,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db_session.add(auth_session)
    db_session.commit()
    db_session.refresh(auth_session)
    return auth_session, token


def validate_and_touch_session(
    db_session: Session, token: str | None, *, ip_address: str, user_agent: str
) -> AuthSession | None:
    """Look up `token`, slide its expiry forward and refresh last-seen/IP/user-agent, and
    return it — `None` if missing, unknown, or expired. Called once per page navigation
    (`/auth/sessions/validate`), the one place a session's lifetime is extended."""
    auth_session = _find_valid_session(db_session, token)
    if auth_session is None:
        return None
    now = _utcnow()
    auth_session.last_seen_at = now
    auth_session.expires_at = now + SESSION_TTL
    auth_session.ip_address = ip_address
    auth_session.user_agent = user_agent
    db_session.add(auth_session)
    db_session.commit()
    db_session.refresh(auth_session)
    return auth_session


def is_session_valid(db_session: Session, token: str | None) -> bool:
    """Read-only validity check for the `api_app`-wide access gate, called on every
    proxied backend call — doesn't write, unlike `validate_and_touch_session`, which
    already extended the session's lifetime once at page-load time."""
    return _find_valid_session(db_session, token) is not None


def _find_valid_session(db_session: Session, token: str | None) -> AuthSession | None:
    if not token:
        return None
    auth_session = db_session.exec(
        select(AuthSession).where(AuthSession.token_hash == _hash_token(token))
    ).first()
    if auth_session is None or auth_session.expires_at < _utcnow():
        return None
    return auth_session


def list_sessions(db_session: Session) -> list[AuthSession]:
    """Every active session, most recently active first."""
    return list(
        db_session.exec(select(AuthSession).order_by(col(AuthSession.last_seen_at).desc())).all()
    )


def revoke_session(db_session: Session, session_id: int) -> bool:
    auth_session = db_session.get(AuthSession, session_id)
    if auth_session is None:
        return False
    db_session.delete(auth_session)
    db_session.commit()
    return True


def revoke_session_by_token(db_session: Session, token: str | None) -> None:
    """Used by logout — a no-op if `token` doesn't match a session (already logged out)."""
    auth_session = _find_valid_session(db_session, token)
    if auth_session is not None:
        db_session.delete(auth_session)
        db_session.commit()


def revoke_other_sessions(db_session: Session, keep_session_id: int) -> int:
    """Revoke every session except `keep_session_id` (the caller's own). Returns how
    many were revoked."""
    others = list(
        db_session.exec(select(AuthSession).where(AuthSession.id != keep_session_id)).all()
    )
    for auth_session in others:
        db_session.delete(auth_session)
    db_session.commit()
    return len(others)


def get_auth_settings(settings: Settings) -> AuthSettingsRead:
    config = load_or_create_config_file(settings)
    return AuthSettingsRead(
        enabled=config.auth_enabled, username=config.auth_username, api_key=config.auth_api_key
    )


def update_auth_settings(settings: Settings, update: AuthSettingsUpdate) -> AuthSettingsRead:
    """Persist enable/username/password. Raises `ValueError` if `enabled=True` would leave
    the account without a resolvable username+password — that would lock every login out
    with no way back short of editing `config.yaml` by hand. A first-time enable also
    generates the API key, so Settings always has one to show once auth is on."""
    config = load_or_create_config_file(settings)
    password_hash = hash_password(update.password) if update.password else config.auth_password_hash
    username = update.username or config.auth_username
    if update.enabled and not (username and password_hash):
        raise ValueError("Enabling login requires a username and password to be set")
    api_key = config.auth_api_key or generate_api_key()
    updated = update_config_file(
        settings,
        {
            "auth_enabled": update.enabled,
            "auth_username": username,
            "auth_password_hash": password_hash,
            "auth_api_key": api_key,
        },
    )
    return AuthSettingsRead(
        enabled=updated.auth_enabled, username=updated.auth_username, api_key=updated.auth_api_key
    )


def regenerate_api_key(settings: Settings) -> AuthSettingsRead:
    updated = update_config_file(settings, {"auth_api_key": generate_api_key()})
    return AuthSettingsRead(
        enabled=updated.auth_enabled, username=updated.auth_username, api_key=updated.auth_api_key
    )


def verify_api_key(settings: Settings, api_key: str | None) -> bool:
    """Constant-time compare so a mismatch can't be timed to leak how many leading
    characters matched."""
    if not api_key:
        return False
    config = load_or_create_config_file(settings)
    return bool(config.auth_api_key) and hmac.compare_digest(api_key, config.auth_api_key)
