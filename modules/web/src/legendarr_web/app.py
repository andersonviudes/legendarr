from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from legendarr_web.arr_services.router import router as arr_services_router
from legendarr_web.dashboard.router import router as dashboard_router
from legendarr_web.history.router import router as history_router
from legendarr_web.language_profiles.router import router as language_profiles_router
from legendarr_web.media_library.router import router as media_library_router
from legendarr_web.subtitle_acquisition.router import router as subtitle_acquisition_router
from legendarr_web.subtitle_proxies.router import router as subtitle_proxies_router
from legendarr_web.system.router import router as system_router

STATIC_DIR = Path(__file__).parent / "static"


def create_app() -> FastAPI:
    app = FastAPI(title="legendarr")
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    app.include_router(dashboard_router)
    app.include_router(media_library_router)
    app.include_router(language_profiles_router)
    app.include_router(arr_services_router)
    app.include_router(subtitle_acquisition_router)
    app.include_router(subtitle_proxies_router)
    app.include_router(history_router)
    app.include_router(system_router)
    return app


app = create_app()
