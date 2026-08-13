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
    """

    release_name: str
    download_id: str
    language: str
    page_link: str | None = None


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
        content and can't search without an episode number); every other provider
        ignores them the same way it ignores an unused `imdb_id`/`moviehash`.

        `video_path` is the local video file itself, for a provider whose lookup needs
        to read the raw file rather than search by metadata — Napiprojekt is the first
        (its hash is a different algorithm than `moviehash`, computed from the file
        directly); every other provider ignores it.

        `tvdb_id` is `Series.tvdb_id` for a series search, `None` for a movie search or
        when it isn't set — Anime Tosho is the first provider that needs it (resolving
        an AniDB episode id starts from a TVDB series id); every other provider ignores
        it the same way it ignores an unused `season`/`episode`."""
        ...

    def download(self, result: SubtitleSearchResult) -> str: ...
