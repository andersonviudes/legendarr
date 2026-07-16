from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class MediaItem:
    """A single item (movie or series) tracked by a media library provider."""

    id: int
    title: str
    path: str


class MediaLibraryClient(Protocol):
    """Contract every media library client (Radarr, Sonarr, ...) must satisfy."""

    def list_items(self) -> list[MediaItem]: ...

    def close(self) -> None: ...
