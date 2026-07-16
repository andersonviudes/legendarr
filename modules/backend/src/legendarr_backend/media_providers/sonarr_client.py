from legendarr_backend.media_providers.base import MediaItem
from legendarr_backend.shared_kernel.http_client.client import ProviderHttpClient


class SonarrClient:
    """Thin client over the Sonarr v3 API."""

    def __init__(self, base_url: str, api_key: str) -> None:
        self._http = ProviderHttpClient("Sonarr", base_url, headers={"X-Api-Key": api_key})

    def list_items(self) -> list[MediaItem]:
        return [
            MediaItem(id=item["id"], title=item["title"], path=item.get("path", ""))
            for item in self._http.get_json("/api/v3/series")
        ]

    def close(self) -> None:
        self._http.close()
