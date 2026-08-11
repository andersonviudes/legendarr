from dataclasses import dataclass
from typing import Literal, Protocol

MediaType = Literal["movie", "series"]


@dataclass(frozen=True)
class MetadataResult:
    """What one provider found for a single movie/series. Every field is optional — a
    provider only fills in what it actually has (e.g. IMDb/OMDb never sets `overview`)."""

    overview: str | None = None
    poster_url: str | None = None
    year: int | None = None
    imdb_rating: float | None = None


class MetadataProvider(Protocol):
    """Contract every metadata backend (TheTVDB, IMDb/OMDb) must satisfy."""

    name: str

    def fetch(
        self,
        *,
        media_type: MediaType,
        title: str,
        tvdb_id: int | None,
        imdb_id: str | None,
    ) -> MetadataResult | None: ...

    def close(self) -> None: ...
