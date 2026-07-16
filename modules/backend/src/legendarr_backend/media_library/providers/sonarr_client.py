from legendarr_backend.http_client.client import DEFAULT_TIMEOUT, ProviderHttpClient
from legendarr_backend.media_library.providers.base import MediaItem


class SonarrClient:
    """Thin client over the Sonarr v3 API."""

    def __init__(self, base_url: str, api_key: str, timeout: float = DEFAULT_TIMEOUT) -> None:
        self._http = ProviderHttpClient(
            "Sonarr", base_url, headers={"X-Api-Key": api_key}, timeout=timeout
        )

    def list_items(self) -> list[MediaItem]:
        return [
            MediaItem(id=item["id"], title=item["title"], path=item.get("path", ""))
            for item in self._http.get_json("/api/v3/series")
        ]

    def system_status(self) -> dict:
        return self._http.get_json("/api/v3/system/status")

    def close(self) -> None:
        self._http.close()
