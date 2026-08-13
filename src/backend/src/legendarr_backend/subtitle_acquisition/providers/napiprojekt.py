import logging
from pathlib import Path
from urllib.parse import urlencode

from legendarr_backend.http_client.client import ProviderClientError, ProviderHttpClient
from legendarr_backend.subtitle_acquisition.models import SubtitleProviderConfig
from legendarr_backend.subtitle_acquisition.napiprojekt_hash import (
    compute_napiprojekt_hash,
    napiprojekt_subhash,
)
from legendarr_backend.subtitle_acquisition.providers.base import SubtitleSearchResult

logger = logging.getLogger(__name__)

NAPIPROJEKT_BASE_URL = "https://napiprojekt.pl"

# "Not found"/error marker the API prefixes its response with instead of a real subtitle
# body — confirmed against Bazarr's own `NapiProjektProvider.query`
# (`/home/viudes/projects/bazarr/custom_libs/subliminal/providers/napiprojekt.py:99`).
_NOT_FOUND_PREFIX = b"NPc0"


class NapiprojektProvider:
    """Real Napiprojekt `search()`/`download()` backend, ported from Bazarr's own
    `NapiProjektProvider` (`/home/viudes/projects/bazarr/custom_libs/subliminal/
    providers/napiprojekt.py`, the confirmed-working reference for this API — live
    verification against the real site wasn't reachable from this environment, same
    fallback `connection_tests.py`'s module docstring documents for a provider with no
    official docs).

    Unlike every other provider so far, this one doesn't search by title at all: its
    lookup is a hash of the local video's first 10MB (`napiprojekt_hash.py`), which
    either matches exactly or doesn't — so a search with no `video_path` (nothing to
    hash) is skipped, and language is checked before anything else since the whole site
    is Polish-only (`l=PL`). `title`/`imdb_id`/`season`/`episode` are all ignored; the
    hash applies equally to a movie or a series file.

    No official docs and no credential — one short-lived `ProviderHttpClient` per call,
    same as `YifySubtitlesProvider`/`TVsubtitlesProvider`. Because the API returns the
    subtitle body directly (no separate metadata step, no zip archive), `search()` and
    `download()` each make their own identical GET to confirm/fetch it — the same
    "call the same endpoint twice" shape `YifySubtitlesProvider`/`TVsubtitlesProvider`
    already have across their own page-then-download calls.
    """

    name = "napiprojekt"

    def __init__(self, config: SubtitleProviderConfig) -> None:
        pass

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
    ) -> list[SubtitleSearchResult]:
        """`title`/`imdb_id`/`season`/`episode` are ignored — the hash is the only
        signal this provider searches on. `moviehash` is ignored too: it's OpenSubtitles'
        own algorithm, not Napiprojekt's (see `napiprojekt_hash.py`)."""
        if language.strip().lower() != "pl":
            return []
        if video_path is None or not video_path.is_file():
            logger.debug("napiprojekt search skipped for %r: no local video file to hash", title)
            return []
        napiprojekt_hash = compute_napiprojekt_hash(video_path)
        client = ProviderHttpClient("Napiprojekt", NAPIPROJEKT_BASE_URL)
        try:
            response = client.request("GET", _query_path(napiprojekt_hash, "PL"))
        finally:
            client.close()
        if not response.is_success or response.content.startswith(_NOT_FOUND_PREFIX):
            return []
        return [
            SubtitleSearchResult(
                release_name=video_path.name,
                download_id=napiprojekt_hash,
                language="pl",
            )
        ]

    def download(self, result: SubtitleSearchResult) -> str:
        client = ProviderHttpClient("Napiprojekt", NAPIPROJEKT_BASE_URL)
        try:
            response = client.request(
                "GET", _query_path(result.download_id, result.language.upper())
            )
        finally:
            client.close()
        if not response.is_success or response.content.startswith(_NOT_FOUND_PREFIX):
            raise ProviderClientError(
                f"Napiprojekt download for hash {result.download_id} failed with "
                f"{response.status_code}"
            )
        return response.content.decode("utf-8", errors="replace")


def _query_path(napiprojekt_hash: str, site_language: str) -> str:
    params = {
        "v": "dreambox",
        "kolejka": "false",
        "nick": "",
        "pass": "",
        "napios": "Linux",
        "l": site_language,
        "f": napiprojekt_hash,
        "t": napiprojekt_subhash(napiprojekt_hash),
    }
    return f"/unit_napisy/dl.php?{urlencode(params)}"
