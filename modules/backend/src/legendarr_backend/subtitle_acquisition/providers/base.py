from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class SubtitleSearchResult:
    """One candidate subtitle returned by a provider's search, before any scoring/download.

    `download_id` is an opaque per-provider handle (URL, file id, whatever that provider's
    API needs to fetch it) — the protocol itself never interprets it.
    """

    release_name: str
    download_id: str
    language: str


class SubtitleProvider(Protocol):
    """Contract every subtitle-acquisition backend (OpenSubtitles, Addic7ed, ...) must satisfy."""

    name: str

    def search(self, title: str, language: str) -> list[SubtitleSearchResult]: ...

    def download(self, result: SubtitleSearchResult) -> str: ...
