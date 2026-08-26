from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import partial

import httpx
from fastapi import FastAPI, Request
from legendarr_backend.api import create_api_app
from legendarr_backend.bootstrap import build_scheduler
from legendarr_backend.config.config_file import load_or_create_config_file
from legendarr_backend.config.settings import get_settings
from legendarr_backend.database.engine import get_session, init_db
from legendarr_backend.logging.setup import configure_logging
from legendarr_backend.media_metadata.manage_metadata_provider import (
    ensure_metadata_providers_seeded,
)
from legendarr_backend.media_servers.manage_media_server import ensure_media_servers_seeded
from legendarr_backend.scheduling.queues import JobQueue
from legendarr_backend.subtitle_acquisition.manage_subtitle_provider import (
    ensure_subtitle_providers_seeded,
)
from legendarr_backend.subtitle_discovery.jobs import enqueue_subtitle_scan
from legendarr_backend.subtitle_translation.manage_translation_provider import (
    ensure_translation_providers_seeded,
)
from legendarr_web.app import create_app as create_web_app
from legendarr_web.backend_client.client import get_backend_client, session_headers

configure_logging()


def create_app() -> FastAPI:
    api_app = create_api_app()
    web_app = create_web_app()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # This lifespan's own context runs before the mounted `api_app`'s (which normally
        # applies migrations), so the schema isn't guaranteed to exist yet — call `init_db()`
        # here too (idempotent: it just runs Alembic's "upgrade head", a no-op if already
        # there) before touching the database.
        init_db()
        with get_session() as session:
            ensure_subtitle_providers_seeded(session)
            ensure_metadata_providers_seeded(session)
            ensure_media_servers_seeded(session)
            ensure_translation_providers_seeded(session)
        scheduler = build_scheduler()
        # The webhook/scan routers live on the mounted `api_app`, so the scheduler is
        # exposed on its state — `request.app` inside those routes is `api_app`, not
        # this parent app.
        api_app.state.scheduler = scheduler
        # Same reasoning for the webhook/"Scan Disk" cascade callback: `media_library.jobs`
        # doesn't import `subtitle_discovery.jobs` directly (would couple the two slices to
        # each other, since subtitle_discovery already depends on media_library), so this
        # composition root wires the concrete enqueue in instead, same shape as the
        # scheduler above.
        config = load_or_create_config_file(get_settings())
        api_app.state.cascade_subtitle_scan = partial(
            enqueue_subtitle_scan,
            scheduler,
            queue=JobQueue.SCAN,
            retry_attempts=config.subtitle_scan_retry_attempts,
            retry_delay_seconds=config.subtitle_scan_retry_delay_seconds,
            probe_timeout_seconds=config.embedded_subtitle_probe_timeout_seconds,
            ocr_cue_timeout_seconds=config.ocr_cue_timeout_seconds,
            cascade=True,
        )
        scheduler.start()
        yield
        scheduler.shutdown()

    async def get_in_process_backend_client(
        request: Request,
    ) -> AsyncIterator[httpx.AsyncClient]:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=api_app),
            base_url="http://backend/",
            headers=session_headers(request),
        ) as client:
            yield client

    web_app.dependency_overrides[get_backend_client] = get_in_process_backend_client

    app = FastAPI(title="legendarr", lifespan=lifespan)
    app.mount("/api", api_app)
    app.mount("/", web_app)
    return app


app = create_app()
