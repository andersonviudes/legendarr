import io
import logging
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from zipfile import ZipFile, is_zipfile

from bs4 import BeautifulSoup, Tag

from legendarr_backend.http_client.client import ProviderClientError, ProviderHttpClient
from legendarr_backend.subtitle_acquisition.models import SubtitleProviderConfig
from legendarr_backend.subtitle_acquisition.providers.base import SubtitleSearchResult

logger = logging.getLogger(__name__)

# Same constant `connection_tests.py`'s "Test connection" check hardcodes — kept private
# here rather than imported there, since this provider has no credential concept and
# stays on `_reachability_only`, the same as `tvsubtitles.py`/`yify_subtitles.py`.
_BASE_URL = "https://www.feliratok.eu"

# Supersubtitles is the branding for feliratok.eu, a Hungarian subtitle site — these are
# the only two languages it serves, site's own display names. Ported from Bazarr's own
# `SuperSubtitlesProvider.get_language` (`/home/viudes/projects/bazarr/custom_libs/
# subliminal_patch/providers/supersubtitles.py:175-181`), the confirmed-working
# reference for this site — no public API docs exist.
_LANGUAGE_NAMES: dict[str, str] = {
    "hu": "Magyar",
    "en": "Angol",
}

_YEAR_SUFFIX_RE = re.compile(r"\s*\(\d{4}\)\s*$")
_FELIRAT_ID_RE = re.compile(r"felirat=(\d+)")


class SupersubtitlesProvider:
    """Real Supersubtitles (feliratok.eu) `search()`/`download()` backend, ported from
    Bazarr's own `SuperSubtitlesProvider` (`/home/viudes/projects/bazarr/custom_libs/
    subliminal_patch/providers/supersubtitles.py`), the confirmed-working reference —
    no public API docs exist for this site.

    Has real movie and TV content, so it handles both, the same shape as
    `LegendasNetProvider`/`SubsourceProvider`: `season`/`episode` both set means a TV
    search, `imdb_id` set means a movie search, neither means this is a series file
    with no resolved episode and the search is skipped. `moviehash`/`video_path`/
    `tvdb_id` are all ignored — nothing here uses them.

    Series search is two JSON calls (title -> series id via an autocomplete endpoint,
    then series id + season/episode -> a subtitle list) and needs no HTML parsing;
    movie search has no such id-resolution step and instead scrapes an HTML results
    table directly. Both paths share one download URL shape
    (`action=letolt&felirat=<id>`), so `download_id` is always that raw id and
    `download()` doesn't need to know which path a result came from.

    Series title matching is a normalized substring check (like `SubsourceProvider`'s
    `_match_title`), not Bazarr's `guessit`-based one — legendarr has no `guessit`
    dependency, and `match_score.pick_best_match`'s cutoff is the net protecting
    against a wrong pick either way. Bazarr's season-pack fallback (a second search
    with no episode number when an episode-specific search comes back empty) isn't
    ported either — same simplification scope as every other provider here.

    No login/session to hold — one short-lived `ProviderHttpClient` per call, same as
    `TVsubtitlesProvider`/`YifySubtitlesProvider`.
    """

    name = "supersubtitles"

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
        """`moviehash`/`video_path`/`tvdb_id`/`series_imdb_id` are ignored — not used
        here. See the class docstring for how `imdb_id`/`season`/`episode` pick a movie
        search, a TV search, or a skip."""
        site_language = _LANGUAGE_NAMES.get(language.strip().lower())
        if site_language is None:
            return []
        is_series = season is not None and episode is not None
        if not is_series and imdb_id is None:
            logger.debug(
                "supersubtitles search skipped for %r: no movie imdb_id or resolved series episode",
                title,
            )
            return []

        client = ProviderHttpClient("Supersubtitles", _BASE_URL)
        try:
            if is_series:
                series_id = _find_series_id(client, title)
                if series_id is None:
                    return []
                data = client.get_json(
                    f"/index.php?action=xbmc&sid={series_id}&ev={season}&rtol={episode}"
                )
                return _parse_series_subtitles(data, site_language, language)
            params = urlencode({"search": title, "soriSorszam": "", "nyelv": "", "tab": "film"})
            response = client.request("GET", f"/index.php?{params}")
            if not response.is_success:
                return []
            return _parse_movie_subtitles(response.text, site_language, language)
        finally:
            client.close()

    def download(self, result: SubtitleSearchResult) -> str:
        client = ProviderHttpClient("Supersubtitles", _BASE_URL)
        try:
            response = client.request(
                "GET", f"/index.php?action=letolt&felirat={result.download_id}"
            )
            if not response.is_success:
                raise ProviderClientError(
                    f"Supersubtitles download for subtitle {result.download_id} failed "
                    f"with {response.status_code}"
                )
        finally:
            client.close()
        return _extract_subtitle_text(response.content)


def _find_series_id(client: ProviderHttpClient, title: str) -> int | None:
    params = urlencode({"term": title, "nyelv": 0, "action": "autoname"})
    data = client.get_json(f"/index.php?{params}")
    if not isinstance(data, list):
        return None
    return _match_series_id(title, data)


def _match_series_id(title: str, items: list[Any]) -> int | None:
    wanted = title.strip().lower()
    for item in items:
        if not isinstance(item, dict):
            continue
        candidate = _YEAR_SUFFIX_RE.sub("", str(item.get("name") or "")).strip().lower()
        if not candidate or (wanted not in candidate and candidate not in wanted):
            continue
        series_id = item.get("ID")
        if isinstance(series_id, str) and series_id.isdigit():
            return int(series_id)
    return None


def _parse_series_subtitles(
    data: Any, site_language: str, language: str
) -> list[SubtitleSearchResult]:
    if not isinstance(data, dict):
        return []
    results = []
    for item in data.values():
        if not isinstance(item, dict) or item.get("language") != site_language:
            continue
        subtitle_id = item.get("felirat")
        if subtitle_id is None:
            continue
        release_name = str(item.get("nev") or "").strip() or "Supersubtitles"
        download_url = f"{_BASE_URL}/index.php?action=letolt&felirat={subtitle_id}"
        results.append(
            SubtitleSearchResult(
                release_name=release_name,
                download_id=str(subtitle_id),
                language=language,
                page_link=download_url,
            )
        )
    return results


def _parse_movie_subtitles(
    html: str, site_language: str, language: str
) -> list[SubtitleSearchResult]:
    soup = BeautifulSoup(html, "html.parser")
    results = []
    for row in soup.find_all("tr"):
        if not isinstance(row, Tag):
            continue
        result = _parse_movie_row(row, site_language, language)
        if result is not None:
            results.append(result)
    return results


def _parse_movie_row(row: Tag, site_language: str, language: str) -> SubtitleSearchResult | None:
    title_div = row.find("div", class_="eredeti")
    if not isinstance(title_div, Tag):
        return None
    language_tag = row.find("small")
    if not isinstance(language_tag, Tag) or language_tag.get_text().strip() != site_language:
        return None

    links = row.find_all("a", href=True)
    href = links[-1].get("href") if links else None
    if not isinstance(href, str):
        return None
    match = _FELIRAT_ID_RE.search(href)
    if match is None:
        return None
    subtitle_id = match.group(1)

    release_name = title_div.get_text().strip() or "Supersubtitles"
    download_url = f"{_BASE_URL}/index.php?action=letolt&felirat={subtitle_id}"
    return SubtitleSearchResult(
        release_name=release_name,
        download_id=subtitle_id,
        language=language,
        page_link=download_url,
    )


def _extract_subtitle_text(content: bytes) -> str:
    stream = io.BytesIO(content)
    if not is_zipfile(stream):
        # Same fallback `legendas_net.py`'s `_extract_subtitle_text` makes — Bazarr's
        # own `download_subtitle` doesn't always get back a zip either.
        return content.decode("utf-8", errors="replace")
    with ZipFile(stream) as archive:
        for name in archive.namelist():
            if name.lower().endswith((".srt", ".sub")):
                return archive.read(name).decode("utf-8", errors="replace")
    raise ProviderClientError("Supersubtitles archive contained no .srt/.sub file")
