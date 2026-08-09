from contextlib import asynccontextmanager

from fastapi import FastAPI

from legendarr_backend.arr_services.router import router as arr_services_router
from legendarr_backend.database.engine import init_db
from legendarr_backend.language_profiles.router import router as language_profiles_router
from legendarr_backend.media_library.router import router as media_library_router
from legendarr_backend.media_library.webhooks import router as webhooks_router
from legendarr_backend.media_metadata.router import router as media_metadata_router
from legendarr_backend.settings.router import router as settings_router
from legendarr_backend.subtitle_acquisition.proxy_router import router as subtitle_proxy_router
from legendarr_backend.subtitle_acquisition.router import router as subtitle_acquisition_router
from legendarr_backend.subtitle_translation.router import router as translation_provider_router
from legendarr_backend.system.router import router as system_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


def create_api_app() -> FastAPI:
    app = FastAPI(title="legendarr-backend-api", lifespan=lifespan)
    app.include_router(language_profiles_router)
    app.include_router(arr_services_router)
    app.include_router(media_library_router)
    app.include_router(webhooks_router)
    app.include_router(media_metadata_router)
    app.include_router(settings_router)
    app.include_router(subtitle_acquisition_router)
    app.include_router(subtitle_proxy_router)
    app.include_router(translation_provider_router)
    app.include_router(system_router)
    return app
