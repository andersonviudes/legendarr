from datetime import datetime

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
    # Whether a local copy is cached at `/posters/{kind}_{id}.jpg` on `legendarr_web`'s
    # static mount (ROADMAP.md 0.20.0) — `poster_url` is kept for reference/provenance,
    # but templates render this instead, with no hotlink fallback while it's `False`.
    poster_cached: bool = False
    year: int | None = None
    imdb_rating: float | None = None
    genres: list[str] = []


class MovieRead(MediaRead):
    pass


class SeriesRead(MediaRead):
    # Sonarr-only episode counts — no equivalent for a movie.
    episode_count: int | None = None
    episode_file_count: int | None = None
    # Sonarr-only: date the most recently aired episode aired. No equivalent for a movie.
    last_aired: datetime | None = None


class SubtitleRead(BaseModel):
    """One discovered subtitle. `id` addresses it for the per-subtitle "sync timing"
    action; `language`/`origin` are what the badge/row display needs.

    `provider`/`release_name`/`score` come from `AcquiredSubtitle` — `None` for a
    subtitle that was never downloaded from a provider (embedded, manually uploaded, or
    translated). The five `*_matched` flags come off that same subtitle's latest
    `AcquisitionAttempt` (mirrors `match_score.ATTRIBUTE_WEIGHTS`'s five attributes),
    `None` either way for the same reason, or per-attribute when the reference filename
    had nothing to compare (see `AcquisitionAttempt`'s own docstring)."""

    id: int
    language: str
    origin: str
    size_bytes: int
    # `None` for an external subtitle — only an embedded one has a container stream index to
    # join back to its `EmbeddedTrackRead` (see `MediaFileRead.embedded_tracks`).
    track_index: int | None = None
    provider: str | None = None
    release_name: str | None = None
    score: float | None = None
    resolution_matched: bool | None = None
    source_matched: bool | None = None
    codec_matched: bool | None = None
    release_group_matched: bool | None = None
    edition_matched: bool | None = None


class EmbeddedTrackRead(BaseModel):
    """One subtitle track `ffprobe` found in the container, whether or not it was extracted.
    `subtitle` is the matching `SubtitleRead` (its id, score, actions, ...) when `extracted`
    is `True`; `None` for a track skipped because its language wasn't in the profile's
    Source Languages, its codec's extraction/OCR toggle is off, or it's already covered by
    an external subtitle."""

    track_index: int
    language: str
    # See `subtitle_discovery.models.EmbeddedTrack.display_language`.
    display_language: str
    extracted: bool
    subtitle: SubtitleRead | None = None


class MediaFileRead(BaseModel):
    """A `MediaFile` plus the subtitles discovered for it, for a detail-page row."""

    id: int
    relative_path: str
    size_bytes: int
    subtitles: list[SubtitleRead]
    # Every embedded track the container has, extracted or not — see `EmbeddedTrackRead`.
    # A track that was extracted also appears in `subtitles` above (as its `SubtitleRead`);
    # this list is what the subtitles dialog uses to render the full, ticked/unticked table.
    embedded_tracks: list[EmbeddedTrackRead] = []
    # Profile target languages this file has no subtitle for yet — rendered as extra
    # gray pills alongside the real ones (embedded/external) in subtitle_pill_list().
    missing_languages: list[str] = []
    # Whether this file already has a subtitle in one of the profile's source languages —
    # gates the missing/empty pills' "Translate now" action in subtitle_pill_list(), since
    # translating needs a real source subtitle to translate from.
    has_source_subtitle: bool = False


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
    # Target languages with a `PendingSubtitle` already held for this episode — rendered
    # as a distinct pill from a plain "missing" one so a search/upload the user just did
    # doesn't look like it had no effect (see `PendingSubtitle`'s docstring for why there's
    # no `MediaFile`/`Subtitle` row to reflect it in yet).
    pending_languages: list[str] = []


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
    poster_cached: bool = False
    missing_languages: list[str]
    missing_files_count: int


class SubtitleSummaryRead(BaseModel):
    """A bare-bones view of one `Subtitle` — just enough to label it in a picker (the
    timing-sync dialog's "sync using another subtitle" reference select). Deliberately
    narrower than `SubtitleRead`, which also carries acquisition-score fields that don't
    apply here."""

    id: int
    language: str
    origin: str


class SubtitleSearchResourceRead(BaseModel):
    """The manual-search panel's "Resource" info box — the searched file's on-disk
    path and a display-only, reconstructed scene-style release name for it."""

    path: str
    release_name: str


class SubtitleCandidateRead(BaseModel):
    """One manual-search result — everything the UI needs to display it and, on
    download, everything `SubtitleCandidateDownloadInput` needs to re-locate it."""

    provider: str
    release_name: str
    download_id: str
    language: str
    page_link: str | None = None
    score: float
    uploader: str | None = None


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
    embedded_tracks: list[EmbeddedTrackRead] = []
    missing_languages: list[str] = []
    has_source_subtitle: bool = False


class PendingSubtitleAcquisitionResult(BaseModel):
    """Outcome of a manual download/upload for a series episode Sonarr hasn't
    downloaded yet — no `subtitles`/`missing_languages` refresh like
    `SubtitleAcquisitionResult`'s, since there's no `MediaFile` row (and so no
    Subtitles-column badge) to refresh: the episode row starts reflecting it once a
    later scan reconciles the pending subtitle onto the real file."""

    success: bool
    message: str


class SubtitleBlacklistResult(SubtitleAcquisitionResult):
    """Same shape as `SubtitleAcquisitionResult`, plus `media_file_id` — the blacklist
    route is addressed by `subtitle_id` (like sync-timing/translate), not
    `media_file_id` (like download/upload), so the web layer needs it back to target
    the file row's oob swap."""

    media_file_id: int
