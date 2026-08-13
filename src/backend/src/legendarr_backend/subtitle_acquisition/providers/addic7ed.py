import logging
import re
from pathlib import Path
from urllib.parse import quote_plus

from bs4 import BeautifulSoup, Tag

from legendarr_backend.http_client.client import ProviderClientError, ProviderHttpClient
from legendarr_backend.subtitle_acquisition.models import SubtitleProviderConfig
from legendarr_backend.subtitle_acquisition.providers.base import SubtitleSearchResult

logger = logging.getLogger(__name__)

# Same constant `connection_tests.py`'s "Test connection" check uses — owned here since
# this is now the module that does the real, ongoing calling.
ADDIC7ED_BASE_URL = "https://www.addic7ed.com"

# ISO 639-1 (optionally with a region subtag, e.g. "pt-br") -> the display name(s)
# Addic7ed shows in its language column. Most languages just use their plain English
# name; these overrides are Addic7ed's actual exceptions (subliminal's
# `Addic7edConverter`, `/home/viudes/projects/bazarr/custom_libs/subliminal/converters/
# addic7ed.py`) for languages it disambiguates by region/script. Not exhaustive — the
# languages a subtitle workflow is realistically going to see, same scope as
# `subtitle_discovery/language_codes.py`.
_ADDIC7ED_LANGUAGE_NAMES: dict[str, tuple[str, ...]] = {
    "en": ("English",),
    "pt-br": ("Portuguese (Brazilian)",),
    "pt": ("Portuguese",),
    "es": ("Spanish (Spain)", "Spanish (Latin America)", "Spanish"),
    "fr-ca": ("French (Canadian)",),
    "fr": ("French",),
    "de": ("German",),
    "it": ("Italian",),
    "ja": ("Japanese",),
    "ko": ("Korean",),
    "zh": ("Chinese (Simplified)", "Chinese (Traditional)"),
    "ru": ("Russian",),
    "ar": ("Arabic",),
    "nl": ("Dutch",),
    "sv": ("Swedish",),
    "no": ("Norwegian",),
    "da": ("Danish",),
    "fi": ("Finnish",),
    "pl": ("Polish",),
    "tr": ("Turkish",),
    "he": ("Hebrew",),
    "hi": ("Hindi",),
    "th": ("Thai",),
    "vi": ("Vietnamese",),
    "id": ("Indonesian",),
    "cs": ("Czech",),
    "el": ("Greek",),
    "hu": ("Hungarian",),
    "ro": ("Romanian",),
    "uk": ("Ukrainian",),
    "bg": ("Bulgarian",),
    "hr": ("Croatian",),
    "sr": ("Serbian (Cyrillic)", "Serbian (Latin)"),
    "sk": ("Slovak",),
    "sl": ("Slovenian",),
    "ca": ("Català",),
    "eu": ("Euskera",),
    "gl": ("Galego",),
    "ms": ("Malay",),
}


class Addic7edProvider:
    """Real Addic7ed `search()`/`download()` backend. Addic7ed has no JSON API and no
    year/season data is available to disambiguate a search: neither `Movie` nor
    `Series` tracks a release year, and `MediaFile` doesn't track season/episode (see
    ROADMAP 0.6.0) — so this is movies only, title-only matching, with
    `pick_best_match`'s cutoff guarding the rest.

    Unlike `OpenSubtitlesProvider`'s per-call client, this holds one lazily-created,
    logged-in `ProviderHttpClient` for the provider instance's lifetime, since every
    call after login needs the same session cookies. `close()` releases it —
    `acquire_subtitle_for_media_file` closes every provider in its chain that exposes
    one once it's done with them.
    """

    name = "addic7ed"

    def __init__(self, config: SubtitleProviderConfig) -> None:
        self._username = config.username
        self._password = config.password
        self._client: ProviderHttpClient | None = None

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
        """`imdb_id` unset is the orchestrator's own movie/series signal
        (`acquire_media_file_subtitle.py:79`) — a series search is skipped with no
        HTTP calls rather than attempted without the season number Addic7ed's TV
        listing requires. `season`/`episode`/`video_path` are ignored — not used here
        yet."""
        if imdb_id is None:
            logger.debug(
                "addic7ed search skipped for %r: series search needs a season number "
                "that isn't tracked yet",
                title,
            )
            return []
        client = self._authenticated_client()
        movie_id = _find_movie_id(client, title)
        if movie_id is None:
            return []
        return _scrape_movie_subtitles(client, movie_id, language)

    def download(self, result: SubtitleSearchResult) -> str:
        client = self._authenticated_client()
        headers = {"Referer": result.page_link} if result.page_link else None
        response = client.request("GET", f"/{result.download_id}", headers=headers)
        if not response.is_success:
            raise ProviderClientError(
                f"Addic7ed download {result.download_id} failed with {response.status_code}"
            )
        return response.text

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def _authenticated_client(self) -> ProviderHttpClient:
        if self._client is None:
            # Only ever constructed via `resolve_subtitle_provider_chain`, which
            # already filtered to configs with `has_credentials` true for this kind —
            # both fields are guaranteed set here.
            assert self._username is not None
            assert self._password is not None
            client = ProviderHttpClient("Addic7ed", ADDIC7ED_BASE_URL)
            addic7ed_login(client, self._username, self._password)
            self._client = client
        return self._client


def addic7ed_login(client: ProviderHttpClient, username: str, password: str) -> None:
    """Mirrors Bazarr's own login flow (`addic7ed.py:151,181-196`): POST to
    dologin.php, then read the same success/failure signals Bazarr does — a 302 on
    that response means the login was accepted, specific response text means it
    wasn't. Raises instead of returning a bool, so a `search()`/`download()` caller's
    broad `except Exception` (`acquire_media_file_subtitle.py`) treats any login
    failure as "this provider isn't usable right now" and moves to the next one.
    Shared with `connection_tests._test_addic7ed`, which is the same flow with no
    real request to follow it.
    """
    client.request("GET", "/login.php")
    response = client.request(
        "POST",
        "/dologin.php",
        data={
            "username": username,
            "password": password,
            "Submit": "Log in",
            "url": "",
            "remember": "true",
        },
    )
    if "recaptcha" in response.text.lower():
        raise ProviderClientError(
            "Addic7ed is asking for a CAPTCHA — this can't be validated automatically, "
            "log in at addic7ed.com to confirm your credentials"
        )
    if "relax, slow down" in response.text:
        raise ProviderClientError("Addic7ed is rate-limiting login attempts — try again later")
    if "Wrong password" in response.text or "doesn't exist" in response.text:
        raise ProviderClientError("Wrong username or password")
    if response.status_code != 302:
        raise ProviderClientError("Addic7ed didn't accept the login — check your credentials")


def _find_movie_id(client: ProviderHttpClient, title: str) -> str | None:
    """Resolves Addic7ed's internal movie id via its search box, matching the first
    result whose title (year suffix stripped) equals `title` once both are
    normalized. Bazarr's own implementation (`addic7ed.py:265-312`) additionally
    matches on release year to disambiguate same-titled movies; `Movie` doesn't track
    one here (see ROADMAP 0.6.0), so this is title-only and best-effort."""
    response = client.request("GET", f"/search.php?search={quote_plus(title)}")
    if not response.is_success:
        raise ProviderClientError(
            f"Addic7ed movie search for {title!r} failed with {response.status_code}"
        )
    soup = BeautifulSoup(response.text, "html.parser")
    table = soup.find("table", class_="tabel")
    if not isinstance(table, Tag):
        return None
    target = _normalize_title(title)
    for row in table.find_all("tr"):
        if not isinstance(row, Tag):
            continue
        link = row.find("a", href=True)
        if not isinstance(link, Tag):
            continue
        href = link.get("href")
        if not isinstance(href, str) or not href.startswith("movie/"):
            continue
        if _normalize_title(link.get_text()) == target:
            return href.removeprefix("movie/")
    return None


def _scrape_movie_subtitles(
    client: ProviderHttpClient, movie_id: str, language: str
) -> list[SubtitleSearchResult]:
    """Scrapes a movie's subtitle table. Addic7ed's movie page has no semantic
    row/cell classes to select on (unlike its TV show page's `tr.epeven`/`td`
    structure) — this mirrors Bazarr's own positional `.contents` indexing
    (`addic7ed.py:496-578`), the one confirmed-working reference for this
    undocumented markup."""
    page_link = f"{ADDIC7ED_BASE_URL}/movie/{movie_id}"
    response = client.request("GET", f"/movie/{movie_id}")
    if not response.is_success:
        raise ProviderClientError(
            f"Addic7ed movie page {movie_id} failed with {response.status_code}"
        )
    soup = BeautifulSoup(response.text, "html.parser")
    wanted_names = _ADDIC7ED_LANGUAGE_NAMES.get(language.strip().lower(), ())
    results = []
    for table in soup.find_all(
        "table", attrs={"align": "center", "border": "0", "class": "tabel95", "width": "100%"}
    ):
        if not isinstance(table, Tag) or not table.find_all("td", class_="NewsTitle"):
            continue
        result = _parse_movie_subtitle_row(table, page_link, wanted_names)
        if result is not None:
            results.append(result)
    return results


def _parse_movie_subtitle_row(
    table: Tag, page_link: str, wanted_names: tuple[str, ...]
) -> SubtitleSearchResult | None:
    rows = table.contents
    if len(rows) <= 4:
        return None
    row1, row2 = rows[1], rows[4]
    if not isinstance(row1, Tag) or not isinstance(row2, Tag):
        return None
    cells1, cells2 = row1.contents, row2.contents
    if len(cells1) <= 1 or len(cells2) <= 8:
        return None
    version_cell, language_cell, status_cell, download_cell = (
        cells1[1],
        cells2[4],
        cells2[6],
        cells2[8],
    )
    cells = (version_cell, language_cell, status_cell, download_cell)
    if not all(isinstance(cell, Tag) for cell in cells):
        return None
    assert isinstance(version_cell, Tag)
    assert isinstance(language_cell, Tag)
    assert isinstance(status_cell, Tag)
    assert isinstance(download_cell, Tag)

    if "%" in status_cell.get_text():
        return None

    language_name = language_cell.get_text().strip()
    if not any(language_name.startswith(name) for name in wanted_names):
        return None

    version_words = version_cell.get_text().split()
    version_text = " ".join(version_words[1:]) if len(version_words) > 1 else ""
    release_name = version_text.split(",")[0].strip() or "Addic7ed"

    links = download_cell.find_all("a", href=True)
    if not links:
        return None
    href = links[-1].get("href")
    if not isinstance(href, str):
        return None

    return SubtitleSearchResult(
        release_name=release_name,
        download_id=href.removeprefix("/"),
        language=language_name,
        page_link=page_link,
    )


def _normalize_title(title: str) -> str:
    stripped = re.sub(r"\s*\(\d{4}\)\s*$", "", title)
    return re.sub(r"[^a-z0-9]+", " ", stripped.lower()).strip()
