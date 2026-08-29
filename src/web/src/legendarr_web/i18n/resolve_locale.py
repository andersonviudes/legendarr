import httpx
from fastapi import Depends, Request

from legendarr_web.backend_client.client import get_backend_client
from legendarr_web.i18n.timezone import DEFAULT_TIMEZONE, current_timezone
from legendarr_web.i18n.translator import DEFAULT_LOCALE, current_locale
from legendarr_web.settings import service

# Same bootstrap paths `session_guard.py` exempts from auth — the backend's own
# `/settings/general` requires a session once auth is enabled, so these pages get the
# default locale/timezone instead of a doomed backend call on every load.
_EXEMPT_PATHS = {"/login", "/logout"}


async def resolve_locale(
    request: Request, client: httpx.AsyncClient = Depends(get_backend_client)
) -> None:
    """App-wide dependency (ROADMAP.md 0.19.0) registered once in `app.py`'s
    `create_app()` — sets `request.state.locale`/`request.state.timezone` (for direct
    use in `base.html`, same shape as `session_guard.require_authenticated_session`
    setting `request.state.auth_enabled`) and `translator.current_locale`/
    `timezone.current_timezone` (what the `t()` Jinja global and `local_datetime` Jinja
    filter, both registered in `templates/loader.py`, actually read from — `ContextVar`s
    instead of `request.state` so they also work from macros, see `translator.py`).

    Both come off the same `GET /settings/general` payload, so resolving timezone here
    too avoids a second backend round trip for what's otherwise a locale-only dependency.
    """
    if request.url.path in _EXEMPT_PATHS:
        request.state.locale = DEFAULT_LOCALE
        current_locale.set(DEFAULT_LOCALE)
        request.state.timezone = DEFAULT_TIMEZONE
        current_timezone.set(DEFAULT_TIMEZONE)
        return
    general_settings = await service.get_general_settings(client)
    request.state.locale = general_settings["ui_locale"]
    current_locale.set(general_settings["ui_locale"])
    request.state.timezone = general_settings["timezone"]
    current_timezone.set(general_settings["timezone"])
