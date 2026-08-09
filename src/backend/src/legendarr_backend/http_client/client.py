from collections.abc import Callable
from typing import Any

import httpx

DEFAULT_TIMEOUT = 10.0
DEFAULT_RETRIES = 2


class ProviderClientError(Exception):
    """Raised when a request to an external provider integration fails."""


class ProviderHttpClient:
    """Thin httpx wrapper carrying this project's shared timeout/retry/error-handling
    conventions for external provider integrations — Radarr/Sonarr today, later
    subtitle-provider and translation-API clients should be built the same way instead
    of each configuring httpx from scratch.
    """

    def __init__(
        self,
        provider: str,
        base_url: str,
        headers: dict[str, str] | None = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self._provider = provider
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers=headers,
            timeout=timeout,
            transport=httpx.HTTPTransport(retries=DEFAULT_RETRIES),
        )

    def _send(
        self, send: Callable[[], httpx.Response], check_status: bool = True
    ) -> httpx.Response:
        try:
            response = send()
            if check_status:
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ProviderClientError(
                f"{self._provider} request to {exc.request.url} failed with "
                f"{exc.response.status_code}"
            ) from exc
        except httpx.RequestError as exc:
            raise ProviderClientError(
                f"{self._provider} request to {exc.request.url} failed: {exc}"
            ) from exc
        return response

    def get_json(self, path: str) -> Any:
        return self._send(lambda: self._client.get(path)).json()

    def post_json(self, path: str, json: Any) -> Any:
        return self._send(lambda: self._client.post(path, json=json)).json()

    def ping(self, path: str = "/") -> None:
        """Confirm `path` responds without erroring, without parsing the body as JSON —
        for providers with no JSON API to call, where reachability is the only thing
        worth checking. Follows redirects — several reachability-only sites 301 their bare
        domain to a canonical one (e.g. `www.` -> bare, `http` -> `https`), which httpx's
        `raise_for_status()` otherwise treats as a failure even though the site is up."""
        self._send(lambda: self._client.get(path, follow_redirects=True))

    def request(
        self,
        method: str,
        path: str,
        data: dict[str, Any] | None = None,
        follow_redirects: bool = False,
    ) -> httpx.Response:
        """Send a request and return the raw `Response` — for integrations that need
        something get_json/post_json/ping don't expose: a non-JSON form body, or
        inspecting a redirect/cookie-based login flow (Addic7ed). Unlike the other
        helpers, this never raises on a non-2xx status — a 3xx/4xx response here can be
        the *expected* outcome the caller needs to inspect (Addic7ed's login flow reads
        a 302 as success) — only a network-level failure is wrapped as a
        `ProviderClientError`."""
        return self._send(
            lambda: self._client.request(
                method, path, data=data, follow_redirects=follow_redirects
            ),
            check_status=False,
        )

    def close(self) -> None:
        self._client.close()


def describe_error(exc: ProviderClientError) -> str:
    """Turn a raw client error into something a user can act on. A 401/403 almost always
    means the credential is missing or wrong, which is far more useful than a bare status
    code — shared by every "test connection" action (arr_services, subtitle_acquisition).
    """
    cause = exc.__cause__
    if isinstance(cause, httpx.HTTPStatusError) and cause.response.status_code in (401, 403):
        return "The server rejected the API Key — check that it's correct"
    return str(exc)
