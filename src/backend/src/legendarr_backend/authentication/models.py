from datetime import datetime

from sqlmodel import Field, SQLModel


class AuthSession(SQLModel, table=True):
    """A logged-in browser session — ROADMAP.md 0.16.0.

    One row per successful login, not per user (legendarr has a single shared admin
    account, no multi-user model). `token_hash` is a SHA-256 hash of the opaque cookie
    value handed to the browser — the raw token is never persisted, same defense-in-depth
    posture as `security/encrypted_string.py`'s encrypted secrets. `expires_at` slides
    forward on every validated request (see `manage_authentication.py`), so an active
    session never expires mid-use but an abandoned one eventually does.
    """

    id: int | None = Field(default=None, primary_key=True)
    token_hash: str = Field(index=True, unique=True)
    created_at: datetime
    last_seen_at: datetime
    expires_at: datetime
    ip_address: str = Field(default="")
    user_agent: str = Field(default="")
