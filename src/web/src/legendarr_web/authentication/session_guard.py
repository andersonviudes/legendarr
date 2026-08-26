import httpx
from fastapi import Depends, Request

from legendarr_web.authentication import service
from legendarr_web.authentication.cookies import SESSION_COOKIE_NAME
from legendarr_web.backend_client.client import get_backend_client

# `/login`/`/logout` are the bootstrap paths — checked before calling the backend at
# all, since a visitor without a session must still be able to reach the login form.
_EXEMPT_PATHS = {"/login", "/logout"}


class AuthenticationRequiredError(Exception):
    """Raised when the visitor has no valid session and auth is enabled — caught by the
    app-level exception handler in `app.py`, which redirects to `/login` (a plain `303`
    for normal navigation, an `HX-Redirect` for an HTMX request)."""


async def require_authenticated_session(
    request: Request, client: httpx.AsyncClient = Depends(get_backend_client)
) -> None:
    """App-wide dependency (ROADMAP.md 0.16.0) registered once in `app.py`'s
    `create_app()` — applies to every included router automatically, and doesn't apply
    to the `StaticFiles` mount, so CSS/JS/icons load unauthenticated for free.

    Stashes the validation result on `request.state` so templates (the sidebar's
    conditional Logout button) and routes (the Sessions page's "this device" flag) can
    reuse it without another round trip to the backend.
    """
    if request.url.path in _EXEMPT_PATHS:
        return
    token = request.cookies.get(SESSION_COOKIE_NAME)
    result = await service.validate_session(
        client,
        token,
        ip_address=request.client.host if request.client else "",
        user_agent=request.headers.get("user-agent", ""),
    )
    request.state.auth_enabled = result["auth_enabled"]
    request.state.auth_session = result["session"]
    if not result["authenticated"]:
        raise AuthenticationRequiredError
