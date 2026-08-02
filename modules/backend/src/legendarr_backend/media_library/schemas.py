from pydantic import BaseModel


class MediaRead(BaseModel):
    """Fields shared by `MovieRead`/`SeriesRead` — arr-reported status plus whatever
    `media_metadata` has fetched for this item, if any."""

    id: int
    title: str
    monitored: bool
    status: str | None
    quality_profile_name: str | None
    overview: str | None = None
    poster_url: str | None = None
    year: int | None = None
    imdb_rating: float | None = None


class MovieRead(MediaRead):
    pass


class SeriesRead(MediaRead):
    # Sonarr-only episode counts — no equivalent for a movie.
    episode_count: int | None = None
    episode_file_count: int | None = None
