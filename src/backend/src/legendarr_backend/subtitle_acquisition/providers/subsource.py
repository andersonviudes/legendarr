import io
import logging
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from zipfile import ZipFile, is_zipfile

from legendarr_backend.http_client.client import ProviderClientError, ProviderHttpClient
from legendarr_backend.subtitle_acquisition.models import SubtitleProviderConfig
from legendarr_backend.subtitle_acquisition.providers.base import SubtitleSearchResult
from legendarr_backend.subtitle_acquisition.providers.hearing_impaired_tags import (
    contains_hearing_impaired_tag,
)

logger = logging.getLogger(__name__)

SUBSOURCE_API_BASE_URL = "https://api.subsource.net/api/v1"
SUBSOURCE_SITE_BASE_URL = "https://subsource.net"

# legendarr's lowercased language code -> Subsource's own display name, used both as the
# `language` query param (lowercased) and to reverse-map a result back to a code. Ported
# from Bazarr's `SubsourceConverter.from_subsource` (`/home/viudes/projects/bazarr/
# custom_libs/subliminal_patch/converters/subsource.py:13-126`), the confirmed-working
# reference for this API's exact names (typo and all) — not exhaustive, same scope as
# `subtitle_discovery/language_codes.py`.
_SUBSOURCE_LANGUAGE_NAMES: dict[str, str] = {
    "ar": "Arabic",
    "bn": "Bengali",
    "pt-br": "Brazillian Portuguese",
    "bg": "Bulgarian",
    "zh": "Chinese BG code",
    "hr": "Croatian",
    "cs": "Czech",
    "da": "Danish",
    "nl": "Dutch",
    "en": "English",
    "fa": "Farsi_persian",
    "fi": "Finnish",
    "fr": "French",
    "de": "German",
    "el": "Greek",
    "he": "Hebrew",
    "hi": "Hindi",
    "hu": "Hungarian",
    "id": "Indonesian",
    "it": "Italian",
    "ja": "Japanese",
    "ko": "Korean",
    "pl": "Polish",
    "pt": "Portuguese",
    "ro": "Romanian",
    "ru": "Russian",
    "sr": "Serbian",
    "sk": "Slovak",
    "sl": "Slovenian",
    "es": "Spanish",
    "sv": "Swedish",
    "th": "Thai",
    "tr": "Turkish",
    "uk": "Ukrainian",
    "ur": "Urdu",
    "vi": "Vietnamese",
}


class SubsourceProvider:
    """Real Subsource `search()`/`download()` backend, ported from Bazarr's own
    `SubsourceProvider` (`/home/viudes/projects/bazarr/custom_libs/subliminal_patch/
    providers/subsource.py`), the confirmed-working reference for this API — no public
    docs exist for it (the docs page is Cloudflare-gated, per `connection_tests.py`).

    Unlike `SubdlProvider`/`YifySubtitlesProvider`, this provider has real TV content,
    so it handles both movies and series, the same shape as `LegendasNetProvider`:
    `season`/`episode` both set means a TV search, `imdb_id` set means a movie search,
    neither means this is a series file with no resolved episode and the search is
    skipped. legendarr has no per-series `imdb_id` yet
    (`acquire_media_file_subtitle.py:84` only resolves one for `Movie`), so unlike
    Bazarr's reference, the TV branch here always resolves the show by title text
    rather than by IMDb id.

    No session/login to hold — one short-lived `ProviderHttpClient` per call, same as
    `SubdlProvider`. The API is a two-step lookup: resolve a `movieId` from a
    title/imdb search, then search subtitles under that id. Bazarr's reference also
    re-parses each result's release info with `guessit` to disambiguate season packs
    from single episodes; legendarr has no `guessit` dependency, so this instead trusts
    the subtitle search endpoint's own `seasonNumber`/`episodeNumber` filtering plus
    `pick_best_match`'s release-name cutoff (`match_score.py`) — the same
    simplification every other provider here makes.
    """

    name = "subsource"

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
        """`moviehash`/`video_path` are ignored — not used here. See the class
        docstring for how `imdb_id`/`season`/`episode` pick a movie search, a TV
        search, or a skip."""
        language_name = _SUBSOURCE_LANGUAGE_NAMES.get(language.strip().lower())
        if language_name is None:
            return []
        is_series = season is not None and episode is not None
        if not is_series and imdb_id is None:
            logger.debug(
                "subsource search skipped for %r: no movie imdb_id or resolved series episode",
                title,
            )
            return []

        api_key = self._api_key or ""
        client = self._client()
        try:
            search_imdb_id = None if is_series else imdb_id
            search_season = season if is_series else None
            movie_id = _find_movie_id(client, api_key, title, search_imdb_id, search_season)
            if movie_id is None:
                return []
            params: dict[str, Any] = {
                "api_key": api_key,
                "language": language_name.lower(),
                "limit": 100,
                "movieId": movie_id,
            }
            if is_series:
                params["seasonNumber"] = season
                params["episodeNumber"] = episode
            response = client.get_json(f"/subtitles?{urlencode(params)}")
        finally:
            client.close()
        if not isinstance(response, dict) or response.get("success") is False:
            return []
        return [
            result
            for item in response.get("data", [])
            if (result := _parse_result(item, title, language)) is not None
        ]

    def download(self, result: SubtitleSearchResult) -> str:
        client = self._client()
        try:
            params = urlencode({"api_key": self._api_key or ""})
            response = client.request("GET", f"/subtitles/{result.download_id}/download?{params}")
            if not response.is_success:
                raise ProviderClientError(
                    f"Subsource download for subtitle {result.download_id} failed with "
                    f"{response.status_code}"
                )
        finally:
            client.close()
        return _extract_subtitle_text(response.content)

    def _client(self) -> ProviderHttpClient:
        return ProviderHttpClient("Subsource", SUBSOURCE_API_BASE_URL)


def _find_movie_id(
    client: ProviderHttpClient, api_key: str, title: str, imdb_id: str | None, season: int | None
) -> int | None:
    """Resolve a Subsource `movieId`, same two-step shape and imdb-first fallback as
    Bazarr's `search_titles`: an imdb search is tried first when available, falling
    back to a text search only when the imdb search itself returned nothing (not
    merely when nothing matched by title) — same as `search_titles`'s own
    `if imdb_id and not results_dict` fallback condition."""
    if imdb_id is not None:
        imdb_results = _fetch_title_results(
            client, {"api_key": api_key, "searchType": "imdb", "imdb": imdb_id}, season
        )
        if imdb_results:
            return _match_title(title, imdb_results)
    text_results = _fetch_title_results(
        client, {"api_key": api_key, "searchType": "text", "q": title.lower()}, season
    )
    return _match_title(title, text_results)


def _fetch_title_results(
    client: ProviderHttpClient, params: dict[str, Any], season: int | None
) -> list[dict[str, Any]]:
    if season is not None:
        params = {**params, "season": season}
    response = client.get_json(f"/movies/search?{urlencode(params)}")
    if not isinstance(response, dict):
        return []
    data = response.get("data")
    return data if isinstance(data, list) else []


def _match_title(title: str, items: list[dict[str, Any]]) -> int | None:
    wanted = title.strip().lower()
    for item in items:
        candidates = {
            str(item.get("title") or "").lower(),
            str(item.get("alternateTitle") or "").lower(),
        }
        matches = any(
            candidate and (wanted in candidate or candidate in wanted) for candidate in candidates
        )
        if matches:
            movie_id = item.get("movieId")
            if isinstance(movie_id, int):
                return movie_id
    return None


def _parse_result(
    item: dict[str, Any], fallback_title: str, language: str
) -> SubtitleSearchResult | None:
    subtitle_id = item.get("subtitleId")
    if subtitle_id is None:
        return None
    release_info = item.get("releaseInfo")
    if isinstance(release_info, list) and release_info:
        release_name = ", ".join(release_info)
    else:
        release_name = fallback_title
    link = item.get("link")
    hearing_impaired = bool(item.get("hearingImpaired", False)) or contains_hearing_impaired_tag(
        item.get("commentary") or ""
    )
    return SubtitleSearchResult(
        release_name=release_name,
        download_id=str(subtitle_id),
        language=language,
        page_link=f"{SUBSOURCE_SITE_BASE_URL}{link}" if isinstance(link, str) else None,
        hearing_impaired=hearing_impaired,
    )


def _extract_subtitle_text(content: bytes) -> str:
    stream = io.BytesIO(content)
    if not is_zipfile(stream):
        raise ProviderClientError("Subsource download wasn't a valid zip archive")
    with ZipFile(stream) as archive:
        for name in archive.namelist():
            if name.lower().endswith((".srt", ".sub")):
                return archive.read(name).decode("utf-8", errors="replace")
    raise ProviderClientError("Subsource archive contained no .srt/.sub file")
