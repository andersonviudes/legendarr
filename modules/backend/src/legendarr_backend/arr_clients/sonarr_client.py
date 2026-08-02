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

    def _quality_profile_names(self) -> dict[int, str]:
        return {
            profile["id"]: profile["name"]
            for profile in self._http.get_json("/api/v3/qualityprofile")
        }

    def list_items(self) -> list[MediaItem]:
        quality_profile_names = self._quality_profile_names()
        return [
            MediaItem(
                id=item["id"],
                title=item["title"],
                path=item.get("path", ""),
                tvdb_id=item.get("tvdbId"),
                imdb_id=item.get("imdbId"),
                monitored=item.get("monitored", False),
                status=item.get("status"),
                quality_profile_id=item.get("qualityProfileId"),
                quality_profile_name=quality_profile_names.get(item.get("qualityProfileId")),
                episode_count=item.get("statistics", {}).get("episodeCount"),
                episode_file_count=item.get("statistics", {}).get("episodeFileCount"),
            )
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
