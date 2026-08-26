from datetime import datetime

from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str
    # The browser's real IP/user-agent — `legendarr_web` forwards these from the
    # incoming `Request` since backend only ever sees the proxying call's own.
    ip_address: str = ""
    user_agent: str = ""


class LoginResult(BaseModel):
    """Returned on a successful login — `legendarr_web` stores `token` as the browser's
    session cookie value and never sees it again after that (only `token_hash` is kept)."""

    token: str
    expires_at: datetime


class SessionRead(BaseModel):
    id: int
    created_at: datetime
    last_seen_at: datetime
    expires_at: datetime
    ip_address: str
    user_agent: str


class SessionValidateRequest(BaseModel):
    token: str | None = None
    ip_address: str = ""
    user_agent: str = ""


class SessionValidateResult(BaseModel):
    """Whether the caller's cookie is a currently-valid session. `authenticated` is
    always `True` when `auth_enabled` is `False` — auth being off means every request is
    allowed, regardless of `token`."""

    authenticated: bool
    auth_enabled: bool
    session: SessionRead | None = None


class RevokeOtherSessionsResult(BaseModel):
    revoked_count: int


class RevokeOtherSessionsRequest(BaseModel):
    keep_session_id: int


class AuthSettingsRead(BaseModel):
    enabled: bool
    username: str
    api_key: str


class AuthSettingsUpdate(BaseModel):
    """The `/settings/authentication` form's shape. `password` blank means "keep the
    current password" — same convention as `arr_service_form.html`'s API key field."""

    enabled: bool
    username: str
    password: str = ""
