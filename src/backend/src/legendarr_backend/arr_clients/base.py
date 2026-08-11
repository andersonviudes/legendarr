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


@dataclass(frozen=True)
class EpisodeItem:
    """A single episode of a Sonarr series, as reported by its per-episode API.

    `relative_path` is Sonarr's own `episodeFile.relativePath` (relative to the series'
    root folder) — the same convention `MediaFile.relative_path` uses, so the two can be
    matched directly. `None` when the episode has no file yet.
    """

    season_number: int
    episode_number: int
    title: str
    relative_path: str | None


class SeriesLibraryClient(MediaLibraryClient, Protocol):
    """A `MediaLibraryClient` that also exposes per-series episode listing.

    Only Sonarr connections satisfy this — Radarr movies have no episode equivalent, so
    `list_episodes` isn't part of the base `MediaLibraryClient` contract (that would force
    `RadarrClient` to implement a method it has no use for). A `Series` is only ever
    synced from a Sonarr connection (see `sync_media_library.MEDIA_MODEL_BY_TYPE`), so
    `build_client(series' arr_service)` always returns one of these at runtime even
    though its declared return type is the broader `RadarrClient | SonarrClient` union.
    """

    def list_episodes(self, series_id: int) -> list[EpisodeItem]: ...
