import logging
from pathlib import Path
from urllib.parse import quote

from legendarr_backend.http_client.client import (
    DEFAULT_TIMEOUT,
    ProviderClientError,
    ProviderHttpClient,
)

logger = logging.getLogger(__name__)


class PlexMediaServerProvider:
    """Plex Media Server client (self-hosted `base_url`, `X-Plex-Token` auth).

    `notify_subtitle_written` finds the library section whose configured root folder
    covers the video's path (same prefix-match idea as
    `arr_services/path_mapping.py::resolve_local_path`), then does a targeted,
    forced-metadata refresh of just that folder — `force=1` is required for a
    subtitle-only change to actually be picked up, a plain scan only detects new/
    removed/renamed media files. Falls back to a full section refresh if the targeted
    call fails; a path that matches no known section is logged and skipped, not an
    error (there's nothing to refresh Plex doesn't already know about).
    """

    name = "Plex"

    def __init__(self, base_url: str, token: str, timeout: float = DEFAULT_TIMEOUT) -> None:
        self._http = ProviderHttpClient(
            "Plex",
            base_url,
            headers={"X-Plex-Token": token, "Accept": "application/json"},
            timeout=timeout,
        )

    def notify_subtitle_written(self, video_path: Path) -> None:
        section_key = self._find_section(video_path)
        if section_key is None:
            logger.info("Plex: no library section covers %s — skipping refresh", video_path)
            return
        folder = quote(str(video_path.parent), safe="")
        response = self._http.request(
            "GET", f"/library/sections/{section_key}/refresh?path={folder}&force=1"
        )
        if response.is_success:
            return
        logger.warning(
            "Plex: targeted refresh failed (%s) for section %s, falling back to a full refresh",
            response.status_code,
            section_key,
        )
        fallback = self._http.request("GET", f"/library/sections/{section_key}/refresh?force=1")
        if not fallback.is_success:
            raise ProviderClientError(
                f"Plex refresh failed for section {section_key}: {fallback.status_code}"
            )

    def _find_section(self, video_path: Path) -> str | None:
        try:
            body = self._http.get_json("/library/sections")
        except ProviderClientError:
            logger.exception("Plex: failed to list library sections")
            return None
        sections = (body.get("MediaContainer") or {}).get("Directory") or []
        target = str(video_path)
        for section in sections:
            for location in section.get("Location") or []:
                root = (location.get("path") or "").rstrip("/")
                if root and (target == root or target.startswith(root + "/")):
                    return section.get("key")
        return None

    def close(self) -> None:
        self._http.close()
