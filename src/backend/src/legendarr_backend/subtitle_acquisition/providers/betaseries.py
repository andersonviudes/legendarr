import io
import logging
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from zipfile import ZipFile, is_zipfile

from legendarr_backend.http_client.client import ProviderClientError, ProviderHttpClient
from legendarr_backend.subtitle_acquisition.models import SubtitleProviderConfig
from legendarr_backend.subtitle_acquisition.providers.base import SubtitleSearchResult

logger = logging.getLogger(__name__)

# Own private constant, not shared with `connection_tests.py`'s literal — same precedent
# as `supersubtitles.py`/`animekalesi.py` (only the credentialed providers with a real
# login flow export theirs for reuse there).
_BASE_URL = "https://api.betaseries.com"

# BetaSeries' own subtitle "language" field -> ISO 639-1, confirmed against Bazarr's own
# `_translateLanguageCodeToLanguage` (`/home/viudes/projects/bazarr/custom_libs/
# subliminal_patch/providers/betaseries.py:206-210`) — the only two languages it serves.
_SITE_LANGUAGE_TO_ISO = {"vo": "en", "vf": "fr"}

# Bazarr's own dead-link filter (`betaseries.py:138`) — this source shut down, its links
# 404.
_DEAD_SOURCE = "seriessub"


class BetaSeriesProvider:
    """Real BetaSeries (api.betaseries.com) `search()`/`download()` backend, ported from
    Bazarr's own `BetaSeriesProvider` (`/home/viudes/projects/bazarr/custom_libs/
    subliminal_patch/providers/betaseries.py`), the confirmed-working reference.

    Series-only (Bazarr: `video_types = (Episode,)`), and requires `tvdb_id`/`season`/
    `episode` all set — same shape as `AnimeToshoProvider`
    (`providers/animetosho.py:139`). legendarr only ever has the *series* tvdb id
    available (`acquire_media_file_subtitle.py:87`), never a per-episode one, so this
    always uses Bazarr's `shows/episodes` path (`season`+`episode` lookup), never its
    `episodes/display` (single-episode-tvdb-id) path. `imdb_id`/`moviehash`/`video_path`
    are ignored.

    English/French only (`vo`/`vf` in the API's own subtitle payload) — a search for any
    other language is skipped with no HTTP call. Doesn't port Bazarr's
    release-group-aware file picking inside a multi-file archive
    (`_choose_subtitle_with_release_group`) — legendarr has no guessit-derived
    release-group signal anywhere in the call chain, same simplification scope as every
    other provider here; picks the first `.srt`/`.sub` in the archive instead.

    No login/session to hold — one short-lived `ProviderHttpClient` per call, same as
    `TVsubtitlesProvider`/`YifySubtitlesProvider`.
    """

    name = "betaseries"

    def __init__(self, config: SubtitleProviderConfig) -> None:
        self._api_key = config.api_key

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
        """`imdb_id`/`moviehash`/`video_path` are ignored — not used here. See the class
        docstring for why `tvdb_id`/`season`/`episode` are all required and only
        `en`/`fr` are served."""
        if tvdb_id is None or season is None or episode is None:
            logger.debug(
                "betaseries search skipped for %r: no tvdb_id/season/episode resolved", title
            )
            return []
        wanted = language.strip().lower()
        if wanted not in _SITE_LANGUAGE_TO_ISO.values():
            return []

        params = {
            "key": self._api_key or "",
            "thetvdb_id": tvdb_id,
            "season": season,
            "episode": episode,
            "subtitles": 1,
            "v": 3.0,
        }
        client = ProviderHttpClient("BetaSeries", _BASE_URL)
        try:
            response = client.request("GET", f"/shows/episodes?{urlencode(params)}")
        finally:
            client.close()

        if response.status_code == 400:
            errors = response.json().get("errors") or []
            code = errors[0].get("code") if errors else None
            if code == 4001:
                return []
            if code == 1001:
                raise ProviderClientError("BetaSeries rejected the API Token")
            raise ProviderClientError(f"BetaSeries search for {title!r} failed with 400")
        if not response.is_success:
            raise ProviderClientError(
                f"BetaSeries search for {title!r} failed with {response.status_code}"
            )

        body = response.json()
        episodes = body.get("episodes") or []
        if not episodes:
            return []
        subs = episodes[0].get("subtitles") or []
        return [result for sub in subs if (result := _parse_subtitle(sub, wanted)) is not None]

    def download(self, result: SubtitleSearchResult) -> str:
        client = ProviderHttpClient("BetaSeries", _BASE_URL)
        try:
            response = client.request("GET", result.download_id)
            if response.status_code == 404:
                raise ProviderClientError(f"BetaSeries download {result.download_id} returned 404")
            if not response.is_success:
                raise ProviderClientError(
                    f"BetaSeries download {result.download_id} failed with {response.status_code}"
                )
        finally:
            client.close()
        return _extract_subtitle_text(response.content)


def _parse_subtitle(sub: dict[str, Any], wanted: str) -> SubtitleSearchResult | None:
    if _SITE_LANGUAGE_TO_ISO.get(str(sub.get("language", "")).lower()) != wanted:
        return None
    if str(sub.get("source")) == _DEAD_SOURCE:
        return None
    url = sub.get("url")
    if not isinstance(url, str):
        return None
    return SubtitleSearchResult(
        release_name=str(sub.get("file") or "BetaSeries"),
        download_id=url,
        language=wanted,
    )


def _extract_subtitle_text(content: bytes) -> str:
    stream = io.BytesIO(content)
    if not is_zipfile(stream):
        return content.decode("utf-8", errors="replace")
    with ZipFile(stream) as archive:
        for name in archive.namelist():
            if name.lower().endswith((".srt", ".sub")):
                return archive.read(name).decode("utf-8", errors="replace")
    raise ProviderClientError("BetaSeries archive contained no .srt/.sub file")
