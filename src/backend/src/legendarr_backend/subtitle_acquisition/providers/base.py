from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class SubtitleSearchResult:
    """One candidate subtitle returned by a provider's search, before any scoring/download.

    `download_id` is an opaque per-provider handle (URL, file id, whatever that provider's
    API needs to fetch it) — the protocol itself never interprets it. `page_link` is the
    result's source page, when a provider's download needs it as a `Referer` to avoid a
    hotlink block (Addic7ed); providers with no such requirement (OpenSubtitles) leave it
    `None`.

    `hash_matched` is `True` only when the provider's own API independently verified this
    result against a content hash of the local video (OpenSubtitles.com's
    `moviehash_match`) — every other provider leaves it at the default `False`, same as
    "no such signal" rather than "verified not a match". `hearing_impaired` is `None` when
    the provider can't tell (most of them), `True`/`False` when it can — see
    `candidate_evaluation/match_score.py` for how both feed scoring.

    `uploader` is display-only (the manual-search results table) — `None` when the
    provider's response doesn't name one (an anonymous upload, or a provider that
    doesn't track it at all).
    """

    release_name: str
    download_id: str
    language: str
    page_link: str | None = None
    hash_matched: bool = False
    hearing_impaired: bool | None = None
    uploader: str | None = None


class SubtitleProvider(Protocol):
    """Contract every subtitle-acquisition backend (OpenSubtitles, Addic7ed, ...) must satisfy."""

    name: str

    def search(
        self,
        title: str,
        language: str,
        *,
        imdb_id: str | None = None,
        moviehash: str | None = None,
        season: int | None = None,
        episode: int | None = None,
        video_path: Path | None = None,
        tvdb_id: int | None = None,
        series_imdb_id: str | None = None,
    ) -> list[SubtitleSearchResult]:
        """`imdb_id`/`moviehash` are optional extra precision a provider *may* use to
        narrow its search (OpenSubtitles does); a provider with no such lookup just
        ignores them and searches on `title`/`language` alone. Kept on the shared
        signature rather than a provider-specific override so callers (the acquisition
        orchestrator) never need to know which concrete provider they're holding.

        `season`/`episode` are the same idea for a series `MediaFile`'s episode number,
        resolved by the orchestrator via `media_library.locate.resolve_media_file_episode`
        (a live Sonarr lookup) — `None` for a movie search or when that resolution failed.
        TVsubtitles is the first provider that actually needs them (it has no movie
        content and can't search without an episode number); every other provider but
        OpenSubtitles ignores them the same way it ignores an unused `imdb_id`/`moviehash`.

        `video_path` is the local video file itself, for a provider whose lookup needs
        to read the raw file rather than search by metadata — Napiprojekt is the first
        (its hash is a different algorithm than `moviehash`, computed from the file
        directly); every other provider ignores it.

        `tvdb_id` is `Series.tvdb_id` for a series search, `None` for a movie search or
        when it isn't set — Anime Tosho is the first provider that needs it (resolving
        an AniDB episode id starts from a TVDB series id); every other provider ignores
        it the same way it ignores an unused `season`/`episode`.

        `series_imdb_id` is `Series.imdb_id` for a series search, `None` for a movie
        search (which already gets its own precise id via `imdb_id`) or when it isn't
        set — OpenSubtitles is the first provider that needs it: OpenSubtitles.com's API
        treats `imdb_id` as a direct episode/movie lookup, so a series' own id has to
        travel separately as `parent_imdb_id` alongside `season_number`/`episode_number`.
        Every other provider ignores it the same way it ignores an unused `tvdb_id`."""
        ...

    def download(self, result: SubtitleSearchResult) -> str: ...
