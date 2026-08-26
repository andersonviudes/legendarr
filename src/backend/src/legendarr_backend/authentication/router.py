from collections.abc import Iterator

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from legendarr_backend.authentication.manage_authentication import (
    create_session,
    get_auth_settings,
    list_sessions,
    regenerate_api_key,
    revoke_other_sessions,
    revoke_session,
    revoke_session_by_token,
    update_auth_settings,
    validate_and_touch_session,
    verify_login,
)
from legendarr_backend.authentication.models import AuthSession
from legendarr_backend.authentication.schemas import (
    AuthSettingsRead,
    AuthSettingsUpdate,
    LoginRequest,
    LoginResult,
    RevokeOtherSessionsRequest,
    RevokeOtherSessionsResult,
    SessionRead,
    SessionValidateRequest,
    SessionValidateResult,
)
from legendarr_backend.config.settings import get_settings
from legendarr_backend.database.engine import get_session

router = APIRouter(prefix="/auth")


def _get_session() -> Iterator[Session]:
    with get_session() as session:
        yield session


def _session_read(auth_session: AuthSession) -> SessionRead:
    """`AuthSession` -> `SessionRead`, dropping `token_hash` — never exposed outside
    this module, even hashed."""
    assert auth_session.id is not None  # persisted rows always have an id
    return SessionRead(
        id=auth_session.id,
        created_at=auth_session.created_at,
        last_seen_at=auth_session.last_seen_at,
        expires_at=auth_session.expires_at,
        ip_address=auth_session.ip_address,
        user_agent=auth_session.user_agent,
    )


@router.post("/login")
def login(data: LoginRequest, session: Session = Depends(_get_session)) -> LoginResult:
    settings = get_settings()
    if not verify_login(settings, data.username, data.password):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    auth_session, token = create_session(
        session, ip_address=data.ip_address, user_agent=data.user_agent
    )
    return LoginResult(token=token, expires_at=auth_session.expires_at)


@router.post("/logout", status_code=204)
def logout(data: SessionValidateRequest, session: Session = Depends(_get_session)) -> None:
    revoke_session_by_token(session, data.token)


@router.post("/sessions/validate")
def validate_session(
    data: SessionValidateRequest, session: Session = Depends(_get_session)
) -> SessionValidateResult:
    settings = get_settings()
    if not get_auth_settings(settings).enabled:
        return SessionValidateResult(authenticated=True, auth_enabled=False)
    auth_session = validate_and_touch_session(
        session, data.token, ip_address=data.ip_address, user_agent=data.user_agent
    )
    if auth_session is None:
        return SessionValidateResult(authenticated=False, auth_enabled=True)
    return SessionValidateResult(
        authenticated=True, auth_enabled=True, session=_session_read(auth_session)
    )


@router.get("/sessions", response_model=list[SessionRead])
def get_sessions(session: Session = Depends(_get_session)) -> list[SessionRead]:
    return [_session_read(s) for s in list_sessions(session)]


@router.delete("/sessions/{session_id}", status_code=204)
def delete_session(session_id: int, session: Session = Depends(_get_session)) -> None:
    if not revoke_session(session, session_id):
        raise HTTPException(status_code=404, detail="Session not found")


@router.post("/sessions/revoke-others")
def revoke_others(
    data: RevokeOtherSessionsRequest, session: Session = Depends(_get_session)
) -> RevokeOtherSessionsResult:
    count = revoke_other_sessions(session, data.keep_session_id)
    return RevokeOtherSessionsResult(revoked_count=count)


@router.get("/settings")
def read_auth_settings() -> AuthSettingsRead:
    return get_auth_settings(get_settings())


@router.put("/settings")
def save_auth_settings(update: AuthSettingsUpdate) -> AuthSettingsRead:
    try:
        return update_auth_settings(get_settings(), update)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/settings/api-key/regenerate")
def regenerate_key() -> AuthSettingsRead:
    return regenerate_api_key(get_settings())
