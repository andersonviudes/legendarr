import io
import logging
from typing import Any
from urllib.parse import urlencode, urljoin
from zipfile import ZipFile, is_zipfile

from legendarr_backend.http_client.client import ProviderClientError, ProviderHttpClient
from legendarr_backend.subtitle_acquisition.models import SubtitleProviderConfig
from legendarr_backend.subtitle_acquisition.providers.base import SubtitleSearchResult

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.subdl.com"
_DOWNLOAD_BASE_URL = "https://dl.subdl.com"

# legendarr's lowercased language code -> Subdl's own request/response code. Ported from
# Bazarr's `SubdlConverter.from_subdl` (`/home/viudes/projects/bazarr/custom_libs/
# subliminal_patch/converters/subdl.py:9-76`), the confirmed-working reference for this
# API's language codes — not exhaustive, same scope as `subtitle_discovery/language_codes.py`.
_SUBDL_LANGUAGE_CODES: dict[str, str] = {
    "ar": "AR",
    "da": "DA",
    "nl": "NL",
    "en": "EN",
    "fa": "FA",
    "fi": "FI",
    "fr": "FR",
    "id": "ID",
    "it": "IT",
    "no": "NO",
    "ro": "RO",
    "es": "ES",
    "sv": "SV",
    "vi": "VI",
    "sq": "SQ",
    "az": "AZ",
    "be": "BE",
    "bn": "BN",
    "bs": "BS",
    "bg": "BG",
    "my": "MY",
    "ca": "CA",
    "zh": "ZH",
    "hr": "HR",
    "cs": "CS",
    "eo": "EO",
    "et": "ET",
    "ka": "KA",
    "de": "DE",
    "el": "EL",
    "kl": "KL",
    "he": "HE",
    "hi": "HI",
    "hu": "HU",
    "is": "IS",
    "ja": "JA",
    "ko": "KO",
    "ku": "KU",
    "lv": "LV",
    "lt": "LT",
    "mk": "MK",
    "ms": "MS",
    "ml": "ML",
    "pl": "PL",
    "pt": "PT",
    "ru": "RU",
    "sr": "SR",
    "si": "SI",
    "sk": "SK",
    "sl": "SL",
    "tl": "TL",
    "ta": "TA",
    "te": "TE",
    "th": "TH",
    "tr": "TR",
    "uk": "UK",
    "ur": "UR",
    "pt-br": "BR_PT",
}


class SubdlProvider:
    """Real Subdl `search()`/`download()` backend. No login/session to hold — one
    short-lived `ProviderHttpClient` per call, same as `YifySubtitlesProvider`.

    Movies only, like `Addic7edProvider`'s series case and `YifySubtitlesProvider`: a
    search with no `imdb_id` (the orchestrator's series signal,
    `acquire_media_file_subtitle.py:79`) is skipped with no HTTP calls — Subdl's
    per-season TV listing isn't wired in until series data (season/episode) is tracked.
    """

    name = "subdl"

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
    ) -> list[SubtitleSearchResult]:
        """`imdb_id` unset is the orchestrator's own series signal — skipped rather than
        attempted, same as `YifySubtitlesProvider.search`. `season`/`episode` are ignored —
        not used here."""
        if imdb_id is None:
            logger.debug("subdl search skipped for %r: this provider is movies-only", title)
            return []
        subdl_language = _SUBDL_LANGUAGE_CODES.get(language.strip().lower())
        if subdl_language is None:
            return []
        params = {
            "api_key": self._api_key or "",
            "imdb_id": imdb_id,
            "languages": subdl_language,
            "type": "movie",
            "releases": 1,
            # A real, documented Subdl API flag that filters out incompatible image-based/
            # txt subtitles — not an app-identity param. Keeps results text-only, matching
            # legendarr's own constraint until OCR support lands (ROADMAP 0.14.0).
            "bazarr": 1,
        }
        client = self._client()
        try:
            response = client.get_json(f"/api/v1/subtitles?{urlencode(params)}")
        finally:
            client.close()
        if not isinstance(response, dict) or response.get("status") is False:
            return []
        return [
            result
            for item in response.get("subtitles", [])
            if (result := _parse_result(item, title)) is not None
        ]

    def download(self, result: SubtitleSearchResult) -> str:
        client = self._client()
        try:
            download_url = urljoin(_DOWNLOAD_BASE_URL, result.download_id)
            response = client.request("GET", download_url, follow_redirects=True)
            if not response.is_success:
                raise ProviderClientError(
                    f"Subdl download {download_url} failed with {response.status_code}"
                )
        finally:
            client.close()
        return _extract_subtitle_text(response.content)

    def _client(self) -> ProviderHttpClient:
        return ProviderHttpClient("Subdl", _BASE_URL)


def _parse_result(item: dict[str, Any], title: str) -> SubtitleSearchResult | None:
    url = item.get("url")
    if not isinstance(url, str):
        return None
    release_name = ", ".join(item.get("releases") or []) or item.get("name") or title
    page = item.get("subtitlePage")
    return SubtitleSearchResult(
        release_name=release_name,
        download_id=url,
        language=item.get("language", ""),
        page_link=urljoin("https://subdl.com", page) if page else None,
    )


def _extract_subtitle_text(content: bytes) -> str:
    stream = io.BytesIO(content)
    if not is_zipfile(stream):
        raise ProviderClientError("Subdl download wasn't a valid zip archive")
    with ZipFile(stream) as archive:
        for name in archive.namelist():
            if name.lower().endswith((".srt", ".sub")):
                return archive.read(name).decode("utf-8", errors="replace")
    raise ProviderClientError("Subdl archive contained no .srt/.sub file")
