from contextlib import asynccontextmanager

from fastapi import FastAPI
from legendarr_backend.bootstrap import build_scheduler
from legendarr_backend.shared_kernel.api import create_api_app
from legendarr_web.app import create_app as create_web_app


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = build_scheduler()
    scheduler.start()
    yield
    scheduler.shutdown()


def create_app() -> FastAPI:
    app = FastAPI(title="legendarr", lifespan=lifespan)
    app.mount("/api", create_api_app())
    app.mount("/", create_web_app())
    return app


app = create_app()
