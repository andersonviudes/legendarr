from datetime import datetime
from typing import Literal

from sqlalchemy import Column
from sqlmodel import Field, SQLModel

from legendarr_backend.security.encrypted_string import EncryptedString

MEDIA_METADATA_PROVIDER_KINDS = ("tvdb", "imdb", "tmdb")

# Derived from the tuple above rather than hand-duplicated, so the two can't drift apart.
MediaMetadataProviderKind = Literal[*MEDIA_METADATA_PROVIDER_KINDS]


class MetadataProviderConfig(SQLModel, table=True):
    """Registration/credentials for one of the fixed `MEDIA_METADATA_PROVIDER_KINDS`.

    Same fixed-catalog shape as `SubtitleProviderConfig` (one row per kind, seeded at
    startup) — all three kinds here authenticate with an api key only. Unlike subtitle
    providers, new rows seed `enabled=True`: the user asked for all sources on by
    default, so the gate that actually matters is `has_credentials`/`is_configured`.
    """

    id: int | None = Field(default=None, primary_key=True)
    kind: str = Field(index=True, unique=True)
    enabled: bool = Field(default=True)
    api_key: str | None = Field(default=None, sa_column=Column(EncryptedString))
    connection_verified: bool = Field(default=False)

    @property
    def has_credentials(self) -> bool:
        return bool(self.api_key)

    @property
    def is_configured(self) -> bool:
        """Whether the enable toggle should be available at all — both kinds need an
        api key to be usable, so this just mirrors `has_credentials`."""
        return self.has_credentials


class MediaMetadata(SQLModel, table=True):
    """Metadata fetched for one `Movie` or `Series` from the enabled sources above.

    Exactly one of `movie_id`/`series_id` is set, same convention as `MediaFile`. One
    row per media item — refetching overwrites it rather than keeping a row per source,
    since the merge policy (TheTVDB wins overview/poster/year, IMDb only contributes
    `imdb_rating`, TMDb only fills in whatever TheTVDB didn't have) is applied before
    this is written.
    """

    id: int | None = Field(default=None, primary_key=True)
    movie_id: int | None = Field(
        default=None, foreign_key="movie.id", index=True, unique=True, ondelete="CASCADE"
    )
    series_id: int | None = Field(
        default=None, foreign_key="series.id", index=True, unique=True, ondelete="CASCADE"
    )
    overview: str | None = Field(default=None)
    poster_url: str | None = Field(default=None)
    year: int | None = Field(default=None)
    imdb_rating: float | None = Field(default=None)
    fetched_at: datetime
    # Set once `poster_url` has been downloaded and written to `Settings.poster_cache_dir`
    # as `{kind}_{id}.jpg` (ROADMAP.md 0.20.0) — `None` means either no poster, or a
    # download that hasn't succeeded yet. `legendarr_web`'s templates use this (surfaced as
    # `poster_cached` on the read schemas) to decide whether to render the locally-served
    # image instead of nothing at all; there's no hotlink fallback to `poster_url` by
    # design, see `media_library/list_media_library.py::metadata_fields`.
    poster_cached_at: datetime | None = Field(default=None)
