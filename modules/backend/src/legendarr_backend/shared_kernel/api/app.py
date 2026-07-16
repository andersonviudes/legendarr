from contextlib import asynccontextmanager

from fastapi import FastAPI

from legendarr_backend.language_profiles.router import router as language_profiles_router
from legendarr_backend.shared_kernel.database.engine import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


def create_api_app() -> FastAPI:
    app = FastAPI(title="legendarr-backend-api", lifespan=lifespan)
    app.include_router(language_profiles_router)
    return app
