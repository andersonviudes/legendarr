from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from legendarr_web.arr_services.router import router as arr_services_router
from legendarr_web.authentication.router import router as authentication_router
from legendarr_web.authentication.session_guard import (
    AuthenticationRequiredError,
    require_authenticated_session,
)
from legendarr_web.dashboard.router import router as dashboard_router
from legendarr_web.history.router import router as history_router
from legendarr_web.i18n.resolve_locale import resolve_locale
from legendarr_web.language_profiles.router import router as language_profiles_router
from legendarr_web.media_library.router import router as media_library_router
from legendarr_web.media_metadata.router import router as media_metadata_router
from legendarr_web.media_servers.router import router as media_servers_router
from legendarr_web.settings.router import authentication_router as auth_settings_router
from legendarr_web.settings.router import general_router as general_settings_router
from legendarr_web.settings.router import router as settings_router
from legendarr_web.subtitle_acquisition.router import router as subtitle_acquisition_router
from legendarr_web.subtitle_proxies.router import router as subtitle_proxies_router
from legendarr_web.subtitle_translation.router import router as translation_provider_router
from legendarr_web.system.router import router as system_router

STATIC_DIR = Path(__file__).parent / "static"


def create_app() -> FastAPI:
    app = FastAPI(
        title="legendarr",
        dependencies=[Depends(require_authenticated_session), Depends(resolve_locale)],
    )
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    app.include_router(authentication_router)
    app.include_router(dashboard_router)
    app.include_router(media_library_router)
    app.include_router(language_profiles_router)
    app.include_router(arr_services_router)
    app.include_router(subtitle_acquisition_router)
    app.include_router(subtitle_proxies_router)
    app.include_router(media_metadata_router)
    app.include_router(media_servers_router)
    app.include_router(translation_provider_router)
    app.include_router(settings_router)
    app.include_router(auth_settings_router)
    app.include_router(general_settings_router)
    app.include_router(history_router)
    app.include_router(system_router)

    @app.exception_handler(AuthenticationRequiredError)
    async def _redirect_to_login(request: Request, exc: AuthenticationRequiredError) -> Response:
        login_url = f"/login?next={request.url.path}"
        if request.headers.get("HX-Request") == "true":
            return Response(status_code=200, headers={"HX-Redirect": login_url})
        return RedirectResponse(login_url, status_code=303)

    return app


app = create_app()
