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

    def __init__(self, provider: str, base_url: str, headers: dict[str, str] | None = None) -> None:
        self._provider = provider
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers=headers,
            timeout=DEFAULT_TIMEOUT,
            transport=httpx.HTTPTransport(retries=DEFAULT_RETRIES),
        )

    def get_json(self, path: str) -> Any:
        try:
            response = self._client.get(path)
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
        return response.json()

    def close(self) -> None:
        self._client.close()
