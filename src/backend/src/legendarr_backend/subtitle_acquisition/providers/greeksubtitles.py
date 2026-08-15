import io
from pathlib import Path
from urllib.parse import urlencode, urljoin
from zipfile import ZipFile, is_zipfile

from bs4 import BeautifulSoup, Tag

from legendarr_backend.http_client.client import ProviderClientError, ProviderHttpClient
from legendarr_backend.subtitle_acquisition.models import SubtitleProviderConfig
from legendarr_backend.subtitle_acquisition.providers.base import SubtitleSearchResult

_SEARCH_BASE_URL = "http://gr.greek-subtitles.com"
_DOWNLOAD_BASE_URL = "http://www.greeksubtitles.info"

_LANGUAGES = {"el", "en"}


class GreekSubtitlesProvider:
    """Real GreekSubtitles (gr.greek-subtitles.com) `search()`/`download()` backend,
    ported from Bazarr's own `GreekSubtitlesProvider` (`/home/viudes/projects/bazarr/
    custom_libs/subliminal_patch/providers/greeksubtitles.py`), the confirmed-working
    reference — no official API exists for this site, everything is scraped HTML.

    Greek/English only, matched directly against the site's own image-flag alpha2 codes
    — no display-name table needed, unlike `YifySubtitlesProvider`/
    `SupersubtitlesProvider`. Has real movie and TV content, both served by the same
    single query: `title` alone for a movie (or a series file with no resolved episode),
    `title + " S{season:02d}E{episode:02d}"` when both are set — unlike
    `SupersubtitlesProvider`'s two-code-path split, there's nothing here to pick wrong,
    so a search is never skipped for "ambiguous" input, only for an unsupported
    `language`. `imdb_id`/`moviehash`/`video_path`/`tvdb_id` are all ignored.

    Only the first results page is fetched — Bazarr's own `query()` follows "Next"
    pagination links indefinitely; dropped as the same kind of simplification already
    applied elsewhere (season-pack fallback, guessit matching), with
    `match_score.pick_best_match` still the net against a wrong pick from a partial
    result set.

    Downloads come from a different host (`greeksubtitles.info`) than search
    (`gr.greek-subtitles.com`), with a `Referer` header pointing back at the search
    result's own page — Bazarr's own anti-hotlink requirement for this site.

    No login/session to hold — one short-lived `ProviderHttpClient` per call, same as
    `TVsubtitlesProvider`/`YifySubtitlesProvider`.
    """

    name = "greeksubtitles"

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
        tvdb_id: int | None = None,
    ) -> list[SubtitleSearchResult]:
        """`imdb_id`/`moviehash`/`video_path`/`tvdb_id` are ignored — not used here. See
        the class docstring for how `season`/`episode` refine the query, and why only
        `el`/`en` are served."""
        wanted = language.strip().lower()
        if wanted not in _LANGUAGES:
            return []
        query = title
        if season is not None and episode is not None:
            query = f"{query} S{season:02d}E{episode:02d}"

        client = ProviderHttpClient("GreekSubtitles", _SEARCH_BASE_URL)
        try:
            response = client.request("GET", f"/search.php?{urlencode({'name': query})}")
        finally:
            client.close()
        if not response.is_success:
            return []
        return _parse_search_results(response.text, wanted)

    def download(self, result: SubtitleSearchResult) -> str:
        client = ProviderHttpClient("GreekSubtitles", _DOWNLOAD_BASE_URL)
        try:
            headers = {"Referer": result.page_link} if result.page_link else None
            response = client.request("GET", f"/getp.php?id={result.download_id}", headers=headers)
            if not response.is_success:
                raise ProviderClientError(
                    f"GreekSubtitles download for subtitle {result.download_id} failed "
                    f"with {response.status_code}"
                )
        finally:
            client.close()
        return _extract_subtitle_text(response.content)


def _parse_search_results(html: str, wanted_language: str) -> list[SubtitleSearchResult]:
    soup = BeautifulSoup(html, "html.parser")
    results = []
    for cell in soup.find_all("td", class_="latest_name"):
        if not isinstance(cell, Tag):
            continue
        result = _parse_result_cell(cell, wanted_language)
        if result is not None:
            results.append(result)
    return results


def _parse_result_cell(cell: Tag, wanted_language: str) -> SubtitleSearchResult | None:
    link = cell.find("a", href=True)
    if not isinstance(link, Tag):
        return None
    href = link.get("href")
    if not isinstance(href, str):
        return None
    segments = href.rsplit("/", 2)
    if len(segments) < 2 or not segments[1].isdigit():
        return None
    subtitle_id = segments[1]

    image = cell.find("img")
    if not isinstance(image, Tag):
        return None
    src = image.get("src")
    if not isinstance(src, str):
        return None
    language_code = src.rsplit("/", 1)[-1].split(".")[0].strip().lower()
    if language_code != wanted_language:
        return None

    release_name = link.get_text().strip() or "GreekSubtitles"
    page_link = urljoin(_SEARCH_BASE_URL, href)
    return SubtitleSearchResult(
        release_name=release_name,
        download_id=subtitle_id,
        language=wanted_language,
        page_link=page_link,
    )


def _extract_subtitle_text(content: bytes) -> str:
    stream = io.BytesIO(content)
    if not is_zipfile(stream):
        # Same fallback `supersubtitles.py`'s `_extract_subtitle_text` makes — Bazarr's
        # own `download_subtitle` for this site isn't guaranteed to get back a zip either.
        return content.decode("utf-8", errors="replace")
    with ZipFile(stream) as archive:
        for name in archive.namelist():
            if name.lower().endswith((".srt", ".sub")):
                return archive.read(name).decode("utf-8", errors="replace")
    raise ProviderClientError("GreekSubtitles archive contained no .srt/.sub file")
