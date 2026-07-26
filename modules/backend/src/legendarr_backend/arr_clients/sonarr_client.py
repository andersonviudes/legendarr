from datetime import datetime

from legendarr_backend.arr_clients.base import (
    DOWNLOAD_FOLDER_IMPORTED_EVENT_TYPE,
    MediaItem,
)
from legendarr_backend.http_client.client import DEFAULT_TIMEOUT, ProviderHttpClient


class SonarrClient:
    """Thin client over the Sonarr v3 API."""

    _HISTORY_PATH = (
        "/api/v3/history"
        f"?eventType={DOWNLOAD_FOLDER_IMPORTED_EVENT_TYPE}"
        "&sortKey=date&sortDirection=descending&pageSize=100"
    )

    def __init__(self, base_url: str, api_key: str, timeout: float = DEFAULT_TIMEOUT) -> None:
        self._http = ProviderHttpClient(
            "Sonarr", base_url, headers={"X-Api-Key": api_key}, timeout=timeout
        )

    def list_items(self) -> list[MediaItem]:
        return [
            MediaItem(id=item["id"], title=item["title"], path=item.get("path", ""))
            for item in self._http.get_json("/api/v3/series")
        ]

    def list_recent_import_ids(self, since: datetime) -> list[int]:
        """Ids of series with episodes imported since `since` (tz-aware).

        Capped at the 100 most recent imports — a bigger burst inside the window
        loses the oldest ones and is left for the next full library scan.
        """
        records = self._http.get_json(self._HISTORY_PATH)["records"]
        return list(
            {
                record["seriesId"]
                for record in records
                if datetime.fromisoformat(record["date"]) >= since
            }
        )

    def system_status(self) -> dict:
        return self._http.get_json("/api/v3/system/status")

    def close(self) -> None:
        self._http.close()
