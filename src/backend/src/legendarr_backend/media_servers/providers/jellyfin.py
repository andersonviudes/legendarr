import logging
from pathlib import Path

from legendarr_backend.http_client.client import (
    DEFAULT_TIMEOUT,
    ProviderClientError,
    ProviderHttpClient,
)

logger = logging.getLogger(__name__)


class JellyfinMediaServerProvider:
    """Jellyfin client (self-hosted `base_url`, `Authorization: MediaBrowser Token=...`
    auth).

    `notify_subtitle_written` reports the *video's* path (not the subtitle's) to
    `/Library/Media/Updated` — Jellyfin resolves the item by path server-side, no
    section/item id lookup needed, and the underlying filesystem watcher has
    historically ignored subtitle-extension-only changes, so the video path is the
    reliable one to send. Falls back to a full `/Library/Refresh` if that call fails.
    """

    name = "Jellyfin"

    def __init__(self, base_url: str, token: str, timeout: float = DEFAULT_TIMEOUT) -> None:
        self._http = ProviderHttpClient(
            "Jellyfin",
            base_url,
            headers={"Authorization": f'MediaBrowser Token="{token}"'},
            timeout=timeout,
        )

    def notify_subtitle_written(self, video_path: Path) -> None:
        response = self._http.request(
            "POST",
            "/Library/Media/Updated",
            json={"Updates": [{"Path": str(video_path), "UpdateType": "Modified"}]},
        )
        if response.is_success:
            return
        logger.warning(
            "Jellyfin: targeted refresh failed (%s), falling back to a full library refresh",
            response.status_code,
        )
        fallback = self._http.request("POST", "/Library/Refresh")
        if not fallback.is_success:
            raise ProviderClientError(f"Jellyfin refresh failed: {fallback.status_code}")

    def close(self) -> None:
        self._http.close()
