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


class SubtitleRead(BaseModel):
    """One discovered subtitle, badge-sized: just what a language pill needs."""

    language: str
    origin: str


class MediaFileRead(BaseModel):
    """A `MediaFile` plus the subtitles discovered for it, for a detail-page row."""

    id: int
    relative_path: str
    size_bytes: int
    subtitles: list[SubtitleRead]


class MediaDetailRead(BaseModel):
    """Fields shared by `MovieDetailRead`/`SeriesDetailRead` on top of `MediaRead`."""

    remote_path: str
    language_profile_name: str | None = None
    target_languages: list[str] = []
    missing_subtitles_count: int


class MovieDetailRead(MovieRead, MediaDetailRead):
    files: list[MediaFileRead]


class EpisodeRead(BaseModel):
    season_number: int
    episode_number: int
    title: str
    media_file: MediaFileRead | None = None


class SeriesDetailRead(SeriesRead, MediaDetailRead):
    episodes: list[EpisodeRead]
    episodes_unavailable: bool = False


class WantedRead(BaseModel):
    """One movie/series with at least one file still missing a target language —
    the library-wide `/media/wanted` view and the dashboard's missing-subtitles count."""

    id: int
    kind: str
    title: str
    poster_url: str | None = None
    missing_languages: list[str]
    missing_files_count: int
