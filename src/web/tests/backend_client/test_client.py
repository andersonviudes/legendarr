import asyncio

import httpx
from legendarr_web.backend_client.client import (
    SESSION_COOKIE_NAME,
    error_detail,
    get_backend_client,
    session_headers,
)
from starlette.requests import Request


def _request_with_cookies(cookies: dict[str, str]) -> Request:
    """A minimal starlette `Request` carrying `cookies` in its header, enough for
    `session_headers`'s `request.cookies.get(...)` lookup — no app or server needed."""
    cookie_header = "; ".join(f"{name}={value}" for name, value in cookies.items())
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [(b"cookie", cookie_header.encode())],
    }
    return Request(scope)


def test_session_headers_forward_the_session_cookie():
    request = _request_with_cookies({SESSION_COOKIE_NAME: "tok"})

    assert session_headers(request) == {"X-Legendarr-Session": "tok"}


def test_session_headers_are_empty_without_a_cookie():
    request = _request_with_cookies({"other": "unrelated"})

    assert session_headers(request) == {}


def test_error_detail_pulls_the_backend_detail_out_of_the_body():
    response = httpx.Response(400, json={"detail": "Name already in use"})
    exc = httpx.HTTPStatusError("Bad Request", request=httpx.Request("GET", "/"), response=response)

    assert error_detail(exc) == "Name already in use"


def test_error_detail_falls_back_without_a_json_body():
    response = httpx.Response(500, text="boom")
    exc = httpx.HTTPStatusError(
        "Server Error", request=httpx.Request("GET", "/"), response=response
    )

    assert error_detail(exc) == "Something went wrong. Please try again."


def test_error_detail_falls_back_without_a_detail_key():
    response = httpx.Response(400, json={"unexpected": "shape"})
    exc = httpx.HTTPStatusError("Bad Request", request=httpx.Request("GET", "/"), response=response)

    assert error_detail(exc) == "Something went wrong. Please try again."


def test_get_backend_client_uses_settings_and_forwards_session_headers(monkeypatch):
    # `get_web_settings` is lru_cached and may already hold the module's default from
    # another test — hand the dependency a fresh settings instance instead.
    from legendarr_web.config.settings import WebSettings

    monkeypatch.setattr(
        "legendarr_web.backend_client.client.get_web_settings",
        lambda: WebSettings(backend_api_url="http://backend:9999/api"),
    )

    async def _drive():
        request = _request_with_cookies({SESSION_COOKIE_NAME: "tok"})
        async for client in get_backend_client(request):
            # httpx appends a trailing slash to base_url — compare normalized.
            assert str(client.base_url).rstrip("/") == "http://backend:9999/api"
            assert client.headers["X-Legendarr-Session"] == "tok"
            return True
        return False

    assert asyncio.run(_drive()) is True
