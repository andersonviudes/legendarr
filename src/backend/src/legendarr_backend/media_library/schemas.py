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
    """One discovered subtitle. `id` addresses it for the per-subtitle "sync timing"
    action; `language`/`origin` are what the badge/row display needs."""

    id: int
    language: str
    origin: str


class MediaFileRead(BaseModel):
    """A `MediaFile` plus the subtitles discovered for it, for a detail-page row."""

    id: int
    relative_path: str
    size_bytes: int
    subtitles: list[SubtitleRead]
    # Profile target languages this file has no subtitle for yet — rendered as extra
    # gray pills alongside the real ones (embedded/external) in subtitle_pill_list().
    missing_languages: list[str] = []


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


class SubtitleCandidateRead(BaseModel):
    """One manual-search result — everything the UI needs to display it and, on
    download, everything `SubtitleCandidateDownloadInput` needs to re-locate it."""

    provider: str
    release_name: str
    download_id: str
    language: str
    page_link: str | None = None
    score: float


class SubtitleCandidateDownloadInput(BaseModel):
    """The candidate fields needed to reconstruct a `SubtitleSearchResult` and pick its
    provider back out of the chain — same fields as `SubtitleCandidateRead` minus
    `score`, which only ever mattered for display/ranking. `target_language` is the
    language the manual search ran in: the sidecar is persisted under it, while
    `language` stays what the provider itself reported (which may format a region
    subtag differently) so providers that locate the download by language still can."""

    provider: str
    release_name: str
    download_id: str
    language: str
    target_language: str
    page_link: str | None = None


class SubtitleAcquisitionResult(BaseModel):
    """Outcome of a manual download/upload — `subtitles` is the media file's fresh
    list, so the web layer can refresh the file row's badges without a second call."""

    success: bool
    message: str
    subtitles: list[SubtitleRead]
    missing_languages: list[str] = []


class SubtitleBlacklistResult(SubtitleAcquisitionResult):
    """Same shape as `SubtitleAcquisitionResult`, plus `media_file_id` — the blacklist
    route is addressed by `subtitle_id` (like sync-timing/translate), not
    `media_file_id` (like download/upload), so the web layer needs it back to target
    the file row's oob swap."""

    media_file_id: int
