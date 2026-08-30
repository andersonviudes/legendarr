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

_BASE_URL = "https://www.animekalesi.com"

# A subtitle listing row's link title looks like "5. Sezon 12. Bölüm Türkçe Altyazısı" —
# season is absent (defaults to 1) for a single-season show. Ported from Bazarr's
# `_parse_season_episode` (`/home/viudes/projects/bazarr/custom_libs/subliminal_patch/
# providers/animekalesi.py:184-199`), the confirmed-working reference for this site — no
# public API exists, everything here is scraped HTML.
_SEASON_RE = re.compile(r"(\d+)\.\s*Sezon")
_EPISODE_RE = re.compile(r"(\d+)\.\s*Bölüm")


class AnimeKalesiProvider:
    """Real AnimeKalesi (animekalesi.com) `search()`/`download()` backend, ported from
    Bazarr's own `AnimeKalesiProvider` (`/home/viudes/projects/bazarr/custom_libs/
    subliminal_patch/providers/animekalesi.py`), the confirmed-working reference — no
    public API exists for this site, everything is scraped HTML.

    Turkish-only, series-only, same shape as `TVsubtitlesProvider`: a search with no
    `season`/`episode` (a movie, or a series file the orchestrator couldn't resolve an
    episode for) is skipped with no HTTP calls, since this site has no movie content and
    no title-only search either. `imdb_id`/`moviehash`/`video_path`/`tvdb_id` are all
    ignored — nothing here uses them.

    Two-step scrape: `/tum-anime-serileri.html` lists every series with a link to its
    `bolumler-*` episode-index page; swapping that page's `bolumler-` for `altyazib-`
    is the subtitle listing, whose rows encode season ("X. Sezon", defaulting to 1 when
    absent) and episode ("Y. Bölüm") in their link title. `search()` returns at most one
    result — the row matching the wanted season/episode — with `download_id` set to that
    row's own page path rather than a final file link, since the real download link
    (`div#altyazi_indir > a`) only exists on that per-episode page; `download()` does the
    extra fetch to resolve it, the same two-hop shape as `TVsubtitlesProvider`'s
    `download-<id>.html` -> archive fetch.

    Series title matching is a normalized substring check (like `SubsourceProvider`'s
    `_match_title`), not Bazarr's Turkish-character-folding/`guessit`-based matching —
    same simplification scope as every other provider here.

    No login/session to hold — one short-lived `ProviderHttpClient` per call, same as
    `TVsubtitlesProvider`/`YifySubtitlesProvider`.
    """

    name = "animekalesi"

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
        series_imdb_id: str | None = None,
    ) -> list[SubtitleSearchResult]:
        """`imdb_id`/`moviehash`/`video_path`/`tvdb_id`/`series_imdb_id` are ignored —
        not used here. See the class docstring for why a missing `season`/`episode`
        skips the search entirely, and only Turkish is served."""
        if language.strip().lower() != "tr":
            return []
        if season is None or episode is None:
            logger.debug("animekalesi search skipped for %r: no season/episode resolved", title)
            return []

        client = ProviderHttpClient("AnimeKalesi", _BASE_URL)
        try:
            series = _find_series(client, title)
            if series is None:
                return []
            series_title, series_path = series
            return _find_episode_result(client, series_title, series_path, season, episode)
        finally:
            client.close()

    def download(self, result: SubtitleSearchResult) -> str:
        client = ProviderHttpClient("AnimeKalesi", _BASE_URL)
        try:
            page_response = client.request("GET", result.download_id)
            if not page_response.is_success:
                raise ProviderClientError(
                    f"AnimeKalesi episode page {result.download_id} failed with "
                    f"{page_response.status_code}"
                )
            download_path = _find_download_path(page_response.text)
            if download_path is None:
                raise ProviderClientError(
                    f"No download link found on AnimeKalesi page {result.download_id}"
                )
            file_response = client.request("GET", download_path)
            if not file_response.is_success:
                raise ProviderClientError(
                    f"AnimeKalesi download {download_path} failed with {file_response.status_code}"
                )
        finally:
            client.close()
        return _extract_subtitle_text(file_response.content)


def _find_series(client: ProviderHttpClient, title: str) -> tuple[str, str] | None:
    response = client.request("GET", "/tum-anime-serileri.html")
    if not response.is_success:
        return None
    soup = BeautifulSoup(response.text, "html.parser")
    wanted = title.strip().lower()
    fallback: tuple[str, str] | None = None
    for cell in soup.find_all("td", id="bolumler"):
        if not isinstance(cell, Tag):
            continue
        link = cell.find("a", href=True)
        if not isinstance(link, Tag):
            continue
        href = link.get("href")
        if not isinstance(href, str) or "bolumler-" not in href:
            continue
        candidate_title = link.get_text().strip()
        candidate = candidate_title.lower()
        if not candidate:
            continue
        if candidate == wanted:
            return candidate_title, _to_path(href)
        if fallback is None and (wanted in candidate or candidate in wanted):
            fallback = (candidate_title, _to_path(href))
    return fallback


def _find_episode_result(
    client: ProviderHttpClient, series_title: str, series_path: str, season: int, episode: int
) -> list[SubtitleSearchResult]:
    listing_path = series_path.replace("bolumler-", "altyazib-")
    response = client.request("GET", listing_path)
    if not response.is_success:
        return []
    soup = BeautifulSoup(response.text, "html.parser")
    for cell in soup.find_all("td", id="ayazi_indir"):
        if not isinstance(cell, Tag):
            continue
        link = cell.find("a", href=True)
        if not isinstance(link, Tag):
            continue
        href = link.get("href")
        link_title = link.get("title")
        if not isinstance(href, str) or "indir_bolum-" not in href:
            continue
        if not isinstance(link_title, str) or "Bölüm Türkçe Altyazısı" not in link_title:
            continue
        row_season, row_episode = _parse_season_episode(link_title)
        if row_season != season or row_episode != episode:
            continue
        episode_path = _to_path(href)
        return [
            SubtitleSearchResult(
                release_name=f"{series_title} - S{season:02d}E{episode:02d}",
                download_id=episode_path,
                language="tr",
                page_link=f"{_BASE_URL}{episode_path}",
            )
        ]
    return []


def _parse_season_episode(text: str) -> tuple[int | None, int | None]:
    episode_match = _EPISODE_RE.search(text)
    if episode_match is None:
        return None, None
    season_match = _SEASON_RE.search(text)
    season = int(season_match.group(1)) if season_match else 1
    return season, int(episode_match.group(1))


def _find_download_path(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    container = soup.find("div", id="altyazi_indir")
    if not isinstance(container, Tag):
        return None
    link = container.find("a", href=True)
    if not isinstance(link, Tag):
        return None
    href = link.get("href")
    return _to_path(href) if isinstance(href, str) else None


def _to_path(href: str) -> str:
    return "/" + href.lstrip("/")


def _extract_subtitle_text(content: bytes) -> str:
    stream = io.BytesIO(content)
    if not is_zipfile(stream):
        # Same fallback `supersubtitles.py`'s `_extract_subtitle_text` makes — AnimeKalesi's
        # own download isn't guaranteed to be a zip either.
        return content.decode("utf-8", errors="replace")
    with ZipFile(stream) as archive:
        for name in archive.namelist():
            if name.lower().endswith((".srt", ".sub")):
                return archive.read(name).decode("utf-8", errors="replace")
    raise ProviderClientError("AnimeKalesi archive contained no .srt/.sub file")
