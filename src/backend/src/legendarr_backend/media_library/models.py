from datetime import datetime
from typing import Literal

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class Movie(SQLModel, table=True):
    """A movie tracked by one of the configured Radarr connections.

    `remote_path` is stored exactly as Radarr reports it — path translation to the
    local filesystem happens at read time via the connection's path mapping, so
    editing the mapping never requires a re-sync.
    """

    __table_args__ = (UniqueConstraint("arr_service_id", "arr_id"),)

    id: int | None = Field(default=None, primary_key=True)
    arr_service_id: int = Field(foreign_key="arrservice.id", index=True, ondelete="CASCADE")
    arr_id: int
    title: str
    remote_path: str
    # Pins this movie to a profile other than whichever one is marked `is_default` —
    # nullable, so most rows fall back to the default instead of needing an explicit link.
    language_profile_id: int | None = Field(
        default=None, foreign_key="languageprofile.id", index=True, ondelete="SET NULL"
    )
    # External catalog ids as reported by Radarr — the fetch keys `media_metadata`'s
    # providers use. Radarr has no `tvdbId` field (its own canonical id system is TMDb),
    # so this is always `None` for a movie.
    tvdb_id: int | None = Field(default=None)
    imdb_id: str | None = Field(default=None)
    # Arr-reported status fields, refreshed on every sync.
    monitored: bool = Field(default=False)
    status: str | None = Field(default=None)
    quality_profile_id: int | None = Field(default=None)
    quality_profile_name: str | None = Field(default=None)
    # Comma-joined, same storage convention as `LanguageProfile.target_languages` —
    # split via `genre_list` below.
    genres: str | None = Field(default=None)

    @property
    def genre_list(self) -> list[str]:
        """`genres` split into names, comma order preserved."""
        return [genre.strip() for genre in (self.genres or "").split(",") if genre.strip()]


class Series(SQLModel, table=True):
    """A series tracked by one of the configured Sonarr connections.

    Same storage contract as `Movie`: the path is kept as Sonarr reports it.
    """

    __table_args__ = (UniqueConstraint("arr_service_id", "arr_id"),)

    id: int | None = Field(default=None, primary_key=True)
    arr_service_id: int = Field(foreign_key="arrservice.id", index=True, ondelete="CASCADE")
    arr_id: int
    title: str
    remote_path: str
    language_profile_id: int | None = Field(
        default=None, foreign_key="languageprofile.id", index=True, ondelete="SET NULL"
    )
    # Sonarr reports both ids directly, so these are populated for every series.
    tvdb_id: int | None = Field(default=None)
    imdb_id: str | None = Field(default=None)
    # Arr-reported status fields, refreshed on every sync.
    monitored: bool = Field(default=False)
    status: str | None = Field(default=None)
    quality_profile_id: int | None = Field(default=None)
    quality_profile_name: str | None = Field(default=None)
    # Sonarr-only episode counts, from the series' `statistics` object.
    episode_count: int | None = Field(default=None)
    episode_file_count: int | None = Field(default=None)
    genres: str | None = Field(default=None)
    # Date the most recently aired episode aired (Sonarr's `previousAiring`).
    last_aired: datetime | None = Field(default=None)

    @property
    def genre_list(self) -> list[str]:
        """`genres` split into names, comma order preserved."""
        return [genre.strip() for genre in (self.genres or "").split(",") if genre.strip()]


class MediaFile(SQLModel, table=True):
    """A video file located on disk for a synced `Movie` or `Series`.

    Exactly one of `movie_id`/`series_id` is set. `relative_path` is stored relative
    to the media item's root folder, so editing a connection's path mapping never
    invalidates rows. Written by the filesystem scan; later consumed by subtitle
    discovery (0.3.0) and the wanted dashboard (0.4.0).
    """

    __table_args__ = (
        UniqueConstraint("movie_id", "relative_path"),
        UniqueConstraint("series_id", "relative_path"),
    )

    id: int | None = Field(default=None, primary_key=True)
    movie_id: int | None = Field(
        default=None, foreign_key="movie.id", index=True, ondelete="CASCADE"
    )
    series_id: int | None = Field(
        default=None, foreign_key="series.id", index=True, ondelete="CASCADE"
    )
    relative_path: str
    size_bytes: int
    scanned_at: datetime


MEDIA_MODEL_BY_TYPE = {"radarr": Movie, "sonarr": Series}

MediaKind = Literal["movie", "series"]
