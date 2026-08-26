from pathlib import Path
from typing import Protocol


class MediaServerProvider(Protocol):
    """Contract every media-server backend (Plex, Jellyfin) must satisfy.

    One method on purpose: how a targeted refresh escalates to a full one (Plex's
    section-matching, Jellyfin's path-based `/Library/Media/Updated`) is entirely
    provider-specific and never needs to leak into the caller. Best-effort — only
    raises `ProviderClientError` when every attempt (targeted and fallback) failed;
    the caller logs and moves on rather than blocking acquisition/translation on it.
    """

    name: str

    def notify_subtitle_written(self, video_path: Path) -> None: ...

    def close(self) -> None: ...
