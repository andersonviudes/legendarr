from fastapi import HTTPException, Request

from legendarr_backend.authentication.manage_authentication import (
    get_auth_settings,
    is_session_valid,
    verify_api_key,
)
from legendarr_backend.config.settings import get_settings
from legendarr_backend.database.engine import get_session

# Path prefixes/paths that never require authentication, checked before anything else.
# `/webhooks/` — Radarr/Sonarr "Connect" calls can't send custom headers, the deliberate
# contract documented on `media_library/webhooks.py`'s own route. The `/auth/...` trio is
# the bootstrap path: you can't already hold a session or API key to ask whether you do.
_EXEMPT_PREFIXES = ("/webhooks/",)
_EXEMPT_PATHS = ("/auth/login", "/auth/logout", "/auth/sessions/validate")


def _is_exempt(path: str) -> bool:
    return path in _EXEMPT_PATHS or any(path.startswith(prefix) for prefix in _EXEMPT_PREFIXES)


def _route_path(request: Request) -> str:
    """The request path relative to wherever `api_app` is mounted.

    `request.url.path` is always the *full* original path — e.g. `/api/webhooks/arr/1`
    when `api_app` is mounted under `/api` (`legendarr_bootstrap/app.py`) — Starlette's
    `Mount` never rewrites `scope["path"]` itself, only `scope["root_path"]` grows as a
    request descends through nested mounts. Exemption checks need the path relative to
    *this* app, so strip `root_path` the same way Starlette's own route matching does.
    """
    path = request.url.path
    root_path = request.scope.get("root_path", "")
    if root_path and path.startswith(root_path):
        return path[len(root_path) :]
    return path


async def require_api_access(request: Request) -> None:
    """App-wide dependency on `api_app` (ROADMAP.md 0.16.0) gating every backend route
    except the exemptions above. A no-op when auth is off. Otherwise passes a request
    that presents either a valid API key (`X-Api-Key` — for scripts, forward-compatible
    with 0.17.0's External API) or a valid session (`X-Legendarr-Session`, forwarded by
    `legendarr_web` on behalf of an already logged-in browser instead of a second shared
    secret between the two processes)."""
    if _is_exempt(_route_path(request)):
        return
    settings = get_settings()
    if not get_auth_settings(settings).enabled:
        return
    if verify_api_key(settings, request.headers.get("X-Api-Key")):
        return
    with get_session() as db_session:
        if is_session_valid(db_session, request.headers.get("X-Legendarr-Session")):
            return
    raise HTTPException(status_code=401, detail="Authentication required")
