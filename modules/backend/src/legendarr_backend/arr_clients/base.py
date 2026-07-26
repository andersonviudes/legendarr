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


class MediaLibraryClient(Protocol):
    """Contract every media library client (Radarr, Sonarr, ...) must satisfy."""

    def list_items(self) -> list[MediaItem]: ...

    def list_recent_import_ids(self, since: datetime) -> list[int]: ...

    def close(self) -> None: ...
