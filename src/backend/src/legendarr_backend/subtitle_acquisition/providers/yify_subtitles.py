import io
import logging
import re
from zipfile import ZipFile, is_zipfile

from bs4 import BeautifulSoup, Tag

from legendarr_backend.http_client.client import ProviderClientError, ProviderHttpClient
from legendarr_backend.subtitle_acquisition.models import SubtitleProviderConfig
from legendarr_backend.subtitle_acquisition.providers.base import SubtitleSearchResult

logger = logging.getLogger(__name__)

# Same constant `connection_tests.py`'s "Test connection" check uses — owned here since
# this is now the module that does the real, ongoing calling.
YIFY_SUBTITLES_BASE_URL = "https://yifysubtitles.ch"

# ISO 639-1 (optionally with a region subtag, e.g. "pt-br") -> the exact display name
# YIFY Subtitles shows in its language column. Ported from Bazarr's own
# `YifySubtitlesProvider.YifyLanguages` (`/home/viudes/projects/bazarr/custom_libs/
# subliminal_patch/providers/yifysubtitles.py:61-100`), which is the confirmed-working
# reference for this site's exact language names — not exhaustive, same scope as
# `subtitle_discovery/language_codes.py`.
_YIFY_LANGUAGE_NAMES: dict[str, str] = {
    "sq": "Albanian",
    "ar": "Arabic",
    "bn": "Bengali",
    "pt-br": "Brazilian Portuguese",
    "bg": "Bulgarian",
    "zh": "Chinese",
    "hr": "Croatian",
    "cs": "Czech",
    "da": "Danish",
    "nl": "Dutch",
    "en": "English",
    "fa": "Farsi/Persian",
    "fi": "Finnish",
    "fr": "French",
    "de": "German",
    "el": "Greek",
    "he": "Hebrew",
    "hu": "Hungarian",
    "id": "Indonesian",
    "it": "Italian",
    "ja": "Japanese",
    "ko": "Korean",
    "lt": "Lithuanian",
    "mk": "Macedonian",
    "ms": "Malay",
    "no": "Norwegian",
    "pl": "Polish",
    "pt": "Portuguese",
    "ro": "Romanian",
    "ru": "Russian",
    "sr": "Serbian",
    "sl": "Slovenian",
    "es": "Spanish",
    "sv": "Swedish",
    "th": "Thai",
    "tr": "Turkish",
    "ur": "Urdu",
    "vi": "Vietnamese",
}


class YifySubtitlesProvider:
    """Real YIFY Subtitles `search()`/`download()` backend. No official API, no
    credential, movies-only — it's the subtitle archive for the YIFY release group, so
    like `Addic7edProvider`'s series case, a search with no `imdb_id` (the orchestrator's
    series signal, `acquire_media_file_subtitle.py:79`) is skipped with no HTTP calls.

    Unlike `Addic7edProvider`, there's no login/session to hold — one short-lived
    `ProviderHttpClient` per call, same as `OpenSubtitlesProvider`.
    """

    name = "yify_subtitles"

    def __init__(self, config: SubtitleProviderConfig) -> None:
        pass

    def search(
        self,
        title: str,
        language: str,
        *,
        imdb_id: str | None = None,
        moviehash: str | None = None,
    ) -> list[SubtitleSearchResult]:
        """`imdb_id` unset is the orchestrator's own series signal — skipped rather than
        attempted, since this site has no series content at all to search."""
        if imdb_id is None:
            logger.debug(
                "yify_subtitles search skipped for %r: this provider is movies-only",
                title,
            )
            return []
        wanted_name = _YIFY_LANGUAGE_NAMES.get(language.strip().lower())
        if wanted_name is None:
            return []
        client = ProviderHttpClient("YIFY Subtitles", YIFY_SUBTITLES_BASE_URL)
        try:
            response = client.request("GET", f"/movie-imdb/{imdb_id}")
        finally:
            client.close()
        if response.status_code != 200:
            # 404 means the imdb id has no page on the site — same "no results" outcome
            # as any other non-200 here, not a provider failure.
            return []
        return _parse_movie_subtitles(response.text, wanted_name)

    def download(self, result: SubtitleSearchResult) -> str:
        client = ProviderHttpClient("YIFY Subtitles", YIFY_SUBTITLES_BASE_URL)
        try:
            headers = {"Referer": result.page_link} if result.page_link else None
            page_response = client.request("GET", f"/{result.download_id}", headers=headers)
            if not page_response.is_success:
                raise ProviderClientError(
                    f"YIFY Subtitles page {result.download_id} failed with "
                    f"{page_response.status_code}"
                )
            download_href = _find_download_href(page_response.text)
            if download_href is None:
                raise ProviderClientError(
                    f"No download link found on YIFY Subtitles page {result.page_link}"
                )
            archive_response = client.request("GET", download_href, headers=headers)
            if not archive_response.is_success:
                raise ProviderClientError(
                    f"YIFY Subtitles download {download_href} failed with "
                    f"{archive_response.status_code}"
                )
        finally:
            client.close()
        return _extract_subtitle_text(archive_response.content)


def _parse_movie_subtitles(html: str, wanted_name: str) -> list[SubtitleSearchResult]:
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", class_="other-subs")
    if not isinstance(table, Tag):
        return []
    body = table.find("tbody")
    if not isinstance(body, Tag):
        return []
    results = []
    for row in body.find_all("tr"):
        if not isinstance(row, Tag):
            continue
        result = _parse_subtitle_row(row, wanted_name)
        if result is not None:
            results.append(result)
    return results


def _parse_subtitle_row(row: Tag, wanted_name: str) -> SubtitleSearchResult | None:
    cells = row.find_all("td")
    if len(cells) < 3:
        return None
    language_cell, release_cell = cells[1], cells[2]
    if not isinstance(language_cell, Tag) or not isinstance(release_cell, Tag):
        return None
    if language_cell.get_text().strip() != wanted_name:
        return None

    link = release_cell.find("a", href=True)
    if not isinstance(link, Tag):
        return None
    href = link.get("href")
    if not isinstance(href, str):
        return None

    release_name = re.sub(r"^subtitle\s+", "", release_cell.get_text().strip())
    download_id = href.removeprefix("/")
    return SubtitleSearchResult(
        release_name=release_name or "YIFY Subtitles",
        download_id=download_id,
        language=wanted_name,
        page_link=f"{YIFY_SUBTITLES_BASE_URL}/{download_id}",
    )


def _find_download_href(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    button = soup.find("a", class_="download-subtitle", href=True)
    if not isinstance(button, Tag):
        return None
    href = button.get("href")
    return href if isinstance(href, str) else None


def _extract_subtitle_text(content: bytes) -> str:
    stream = io.BytesIO(content)
    if not is_zipfile(stream):
        raise ProviderClientError("YIFY Subtitles download wasn't a valid zip archive")
    with ZipFile(stream) as archive:
        for name in archive.namelist():
            if name.lower().endswith((".srt", ".sub")):
                return archive.read(name).decode("utf-8", errors="replace")
    raise ProviderClientError("YIFY Subtitles archive contained no .srt/.sub file")
