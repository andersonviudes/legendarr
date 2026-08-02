from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

# Arr history eventType for a completed import (same enum in Radarr and Sonarr).
DOWNLOAD_FOLDER_IMPORTED_EVENT_TYPE = 3


@dataclass(frozen=True)
class MediaItem:
    """A single item (movie or series) tracked by a media library provider."""

    id: int
    title: str
    path: str
    # External catalog ids as reported by the Arr app itself — Sonarr's series payload
    # always has both; Radarr's movie payload never has `tvdbId` (Radarr's own canonical
    # id system is TMDb), so `tvdb_id` stays `None` for every movie.
    tvdb_id: int | None = None
    imdb_id: str | None = None
    monitored: bool = False
    status: str | None = None
    quality_profile_id: int | None = None
    quality_profile_name: str | None = None
    # Sonarr-only: episode counts from the series' `statistics` object. Always `None`
    # for a movie — Radarr has no equivalent per-item metric.
    episode_count: int | None = None
    episode_file_count: int | None = None


class MediaLibraryClient(Protocol):
    """Contract every media library client (Radarr, Sonarr, ...) must satisfy."""

    def list_items(self) -> list[MediaItem]: ...

    def list_recent_import_ids(self, since: datetime) -> list[int]: ...

    def close(self) -> None: ...
