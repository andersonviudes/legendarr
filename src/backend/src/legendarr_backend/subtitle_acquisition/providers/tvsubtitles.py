import io
import logging
import re
from pathlib import Path
from zipfile import ZipFile, is_zipfile

from bs4 import BeautifulSoup, Tag

from legendarr_backend.http_client.client import ProviderClientError, ProviderHttpClient
from legendarr_backend.subtitle_acquisition.models import SubtitleProviderConfig
from legendarr_backend.subtitle_acquisition.providers.base import SubtitleSearchResult

logger = logging.getLogger(__name__)

_BASE_URL = "http://www.tvsubtitles.net"

# ISO 639-1 (optionally with a region subtag) -> TVsubtitles' own 2-letter site code, used
# in its flag-image filenames and its `subtitle-<id>.html`/`download-<id>.html` pages.
# Mostly identity; these overrides are the site's actual exceptions, ported from Bazarr's
# `TVsubtitlesConverter` (`/home/viudes/projects/bazarr/custom_libs/subliminal/converters/
# tvsubtitles.py:9`), the confirmed-working reference for this site's codes — not
# exhaustive, same scope as `subtitle_discovery/language_codes.py`.
_TVSUBTITLES_LANGUAGE_CODES: dict[str, str] = {
    "ar": "ar",
    "bg": "bg",
    "cs": "cz",
    "da": "da",
    "de": "de",
    "el": "gr",
    "en": "en",
    "es": "es",
    "fi": "fi",
    "fr": "fr",
    "hu": "hu",
    "it": "it",
    "ja": "jp",
    "ko": "ko",
    "nl": "nl",
    "pl": "pl",
    "pt": "pt",
    "pt-br": "br",
    "ro": "ro",
    "ru": "ru",
    "sv": "sv",
    "tr": "tr",
    "uk": "ua",
    "zh": "cn",
}

# A show suggestion's link text looks like "Breaking Bad (2008-2013)" (or with a
# trailing "US"/"UK" disambiguator) — ported from Bazarr's `link_re`
# (`subliminal/providers/tvsubtitles.py:25`).
_SHOW_LINK_RE = re.compile(r"^(?P<series>.+?)(?: \(?\d{4}\)?| \((?:US|UK)\))? \(\d{4}-\d{4}\)$")

# The JS on a `download-<id>.html` page assembles the real download link across several
# `sN='...';` assignments — ported from Bazarr's `download_subtitle`
# (`subliminal/providers/tvsubtitles.py:223`).
_DOWNLOAD_LINK_RE = re.compile(r"s\d=\s*'(.*?)';")

_EPISODE_LINK_RE = re.compile(r"^episode-\d+\.html$")


class TVsubtitlesProvider:
    """Real TVsubtitles `search()`/`download()` backend. No official API, no
    credential, series only: title -> show id -> season page -> episode id -> subtitle
    rows, ported from Bazarr's `TVsubtitlesProvider`
    (`/home/viudes/projects/bazarr/custom_libs/subliminal_patch/providers/tvsubtitles.py`,
    the confirmed-working reference this HTML scraping is based on — live verification
    against the real site wasn't reachable from this environment, same fallback
    `connection_tests.py`'s module docstring documents for a provider with no API).

    A search with no `season`/`episode` (the orchestrator's signal that this is either a
    movie or a series file it couldn't resolve an episode for,
    `acquire_media_file_subtitle.py`) is skipped with no HTTP calls — the inverse of
    `YifySubtitlesProvider`/`SubdlProvider`'s `imdb_id is None` skip, since TVsubtitles has
    no movie content at all to fall back to either way.

    No login/session to hold — one short-lived `ProviderHttpClient` per call, same as
    `YifySubtitlesProvider`/`SubdlProvider`.
    """

    name = "tvsubtitles"

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
        """`season`/`episode` unset means either a movie search or a series file the
        orchestrator couldn't resolve an episode for — skipped rather than attempted,
        since TVsubtitles has no title-only or movie search path at all. `video_path` is
        ignored — not used here."""
        if season is None or episode is None:
            logger.debug("tvsubtitles search skipped for %r: no season/episode resolved", title)
            return []
        site_language = _TVSUBTITLES_LANGUAGE_CODES.get(language.strip().lower())
        if site_language is None:
            return []
        client = ProviderHttpClient("TVsubtitles", _BASE_URL)
        try:
            show_id = _find_show_id(client, title)
            if show_id is None:
                return []
            episode_id = _find_episode_id(client, show_id, season, episode)
            if episode_id is None:
                return []
            response = client.request("GET", f"/episode-{episode_id}.html")
            if not response.is_success:
                return []
        finally:
            client.close()
        return _parse_episode_subtitles(response.text, site_language)

    def download(self, result: SubtitleSearchResult) -> str:
        client = ProviderHttpClient("TVsubtitles", _BASE_URL)
        try:
            page_response = client.request("GET", f"/download-{result.download_id}.html")
            if not page_response.is_success:
                raise ProviderClientError(
                    f"TVsubtitles download page {result.download_id} failed with "
                    f"{page_response.status_code}"
                )
            download_href = _find_download_href(page_response.text)
            if download_href is None:
                raise ProviderClientError(
                    f"No download link found on TVsubtitles page {result.page_link}"
                )
            archive_response = client.request("GET", f"/{download_href}")
            if not archive_response.is_success:
                raise ProviderClientError(
                    f"TVsubtitles download {download_href} failed with "
                    f"{archive_response.status_code}"
                )
        finally:
            client.close()
        return _extract_subtitle_text(archive_response.content)


def _find_show_id(client: ProviderHttpClient, title: str) -> int | None:
    response = client.request("POST", "/search1.php", data={"qs": title})
    if not response.is_success:
        return None
    soup = BeautifulSoup(response.text, "html.parser")
    normalized_title = title.strip().lower()
    for link in soup.select('div.left li div a[href^="/tvshow-"]'):
        match = _SHOW_LINK_RE.match(link.get_text().strip())
        if match is None or match.group("series").strip().lower() != normalized_title:
            continue
        href = link.get("href")
        if not isinstance(href, str):
            continue
        show_id = href.removeprefix("/tvshow-").removesuffix(".html")
        if show_id.isdigit():
            return int(show_id)
    return None


def _find_episode_id(
    client: ProviderHttpClient, show_id: int, season: int, episode: int
) -> int | None:
    response = client.request("GET", f"/tvshow-{show_id}-{season}.html")
    if not response.is_success:
        return None
    soup = BeautifulSoup(response.text, "html.parser")
    table = soup.find("table", id="table5")
    if not isinstance(table, Tag):
        return None
    for row in table.find_all("tr"):
        if not isinstance(row, Tag):
            continue
        link = row.find("a", href=_EPISODE_LINK_RE)
        if not isinstance(link, Tag):
            continue
        cells = row.find_all("td")
        if len(cells) < 2 or "x" not in cells[0].get_text():
            continue
        try:
            row_episode = int(cells[0].get_text().strip().split("x")[1])
        except ValueError:
            continue
        if row_episode != episode:
            continue
        href = link.get("href")
        if not isinstance(href, str):
            continue
        episode_id = href.removeprefix("episode-").removesuffix(".html")
        if episode_id.isdigit():
            return int(episode_id)
    return None


def _parse_episode_subtitles(html: str, site_language: str) -> list[SubtitleSearchResult]:
    soup = BeautifulSoup(html, "html.parser")
    results = []
    for row in soup.find_all("div", class_="subtitlen"):
        if not isinstance(row, Tag):
            continue
        result = _parse_subtitle_row(row, site_language)
        if result is not None:
            results.append(result)
    return results


def _parse_subtitle_row(row: Tag, site_language: str) -> SubtitleSearchResult | None:
    header = row.find("h5")
    if not isinstance(header, Tag):
        return None
    image = header.find("img")
    if not isinstance(image, Tag):
        return None
    src = image.get("src")
    if not isinstance(src, str):
        return None
    if src.rsplit("/", 1)[-1].removesuffix(".gif") != site_language:
        return None

    link = row.find_parent("a", href=True)
    if not isinstance(link, Tag):
        return None
    href = link.get("href")
    if not isinstance(href, str):
        return None
    subtitle_id = href.removeprefix("/subtitle-").removesuffix(".html")
    if not subtitle_id.isdigit():
        return None

    rip_cell = row.find("p", title="rip")
    rip = rip_cell.get_text().strip() if isinstance(rip_cell, Tag) else None
    release = header.get_text().strip() or None
    release_name = ", ".join(part for part in (rip, release) if part) or "TVsubtitles"

    return SubtitleSearchResult(
        release_name=release_name,
        download_id=subtitle_id,
        language=site_language,
        page_link=f"{_BASE_URL}/subtitle-{subtitle_id}.html",
    )


def _find_download_href(html: str) -> str | None:
    parts = _DOWNLOAD_LINK_RE.findall(html)
    return "".join(parts) or None


def _extract_subtitle_text(content: bytes) -> str:
    stream = io.BytesIO(content)
    if not is_zipfile(stream):
        raise ProviderClientError("TVsubtitles download wasn't a valid zip archive")
    with ZipFile(stream) as archive:
        for name in archive.namelist():
            if name.lower().endswith((".srt", ".sub")):
                return archive.read(name).decode("utf-8", errors="replace")
    raise ProviderClientError("TVsubtitles archive contained no .srt/.sub file")
