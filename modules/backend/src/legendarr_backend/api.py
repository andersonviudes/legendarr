from contextlib import asynccontextmanager

from fastapi import FastAPI

from legendarr_backend.arr_services.router import router as arr_services_router
from legendarr_backend.database.engine import init_db
from legendarr_backend.language_profiles.router import router as language_profiles_router
from legendarr_backend.subtitle_acquisition.proxy_router import router as subtitle_proxy_router
from legendarr_backend.subtitle_acquisition.router import router as subtitle_acquisition_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


def create_api_app() -> FastAPI:
    app = FastAPI(title="legendarr-backend-api", lifespan=lifespan)
    app.include_router(language_profiles_router)
    app.include_router(arr_services_router)
    app.include_router(subtitle_acquisition_router)
    app.include_router(subtitle_proxy_router)
    return app
