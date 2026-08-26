from collections.abc import AsyncIterator

import httpx
from fastapi import Request

from legendarr_web.authentication.cookies import SESSION_COOKIE_NAME
from legendarr_web.config.settings import get_web_settings


def session_headers(request: Request) -> dict[str, str]:
    """The `X-Legendarr-Session` header to attach to a backend call, forwarding the
    visitor's session cookie so the backend's `api_app`-wide access gate accepts it as
    proof of an already-established login — used both by `get_backend_client` below and
    by `legendarr_bootstrap/app.py`'s in-process override of it (the merged single-process
    deploy talks to the backend via `ASGITransport`, not real HTTP, but still goes through
    the same gate, so it needs the same header)."""
    session_token = request.cookies.get(SESSION_COOKIE_NAME)
    return {"X-Legendarr-Session": session_token} if session_token else {}


async def get_backend_client(request: Request) -> AsyncIterator[httpx.AsyncClient]:
    """The shared client every route uses to reach the backend API."""
    settings = get_web_settings()
    async with httpx.AsyncClient(
        base_url=settings.backend_api_url, headers=session_headers(request)
    ) as client:
        yield client


def error_detail(exc: httpx.HTTPStatusError) -> str:
    """Pull the backend's `detail` message out of an HTTPStatusError's JSON body."""
    try:
        return exc.response.json().get("detail", "Something went wrong. Please try again.")
    except ValueError:
        return "Something went wrong. Please try again."
