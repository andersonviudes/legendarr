import logging
import lzma
import time
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from legendarr_backend.http_client.client import ProviderClientError, ProviderHttpClient
from legendarr_backend.subtitle_acquisition.models import SubtitleProviderConfig
from legendarr_backend.subtitle_acquisition.providers.base import SubtitleSearchResult

logger = logging.getLogger(__name__)

# Same constants `connection_tests.py`'s "Test connection" check uses — owned here since
# this is now the module that does the real, ongoing calling. Three different hosts:
# the feed API this provider searches against, the storage host it downloads from, and
# the real AniDB HTTP API it resolves an episode id through.
ANIMETOSHO_FEED_BASE_URL = "https://feed.animetosho.org"
ANIMETOSHO_STORAGE_BASE_URL = "https://animetosho.org"
ANIDB_API_URL = "http://api.anidb.net:9001/httpapi"

# Bazarr's own default (`AniDBClient.__init__`'s `api_client_ver=1`) — one hardcoded
# knob, not a second user-editable field alongside the API client key (YAGNI).
ANIDB_CLIENT_VERSION = 1

_ANIME_LIST_MAPPING_URL = (
    "https://raw.githubusercontent.com/Anime-Lists/anime-lists/master/anime-list.xml"
)

# AniDB's own soft limit on API requests per day, ported from Bazarr's
# `daily_limit_request_count` (`anidb.py:33`).
_DAILY_QUOTA_LIMIT = 200
_MAPPING_CACHE_TTL_SECONDS = 60 * 60 * 24
_EPISODES_CACHE_TTL_SECONDS = 60 * 60 * 24
# Newest-first cap on how many releases one AniDB episode id's search returns — Bazarr
# exposes this as a user-configurable "search threshold"; legendarr doesn't have that
# setting concept yet, so this is a fixed constant instead (YAGNI).
_ENTRY_LIMIT = 10

_XZ_MAGIC = b"\xfd7zXZ\x00"

# legendarr's lowercased language code -> the alpha3(b) code Anime Tosho's own API
# reports in a subtitle attachment's `info.lang`. Ported from Bazarr's
# `AnimeToshoProvider.supported_languages` (`/home/viudes/projects/bazarr/custom_libs/
# subliminal_patch/providers/animetosho.py:28-46`), the confirmed-working reference for
# this API's language handling — not exhaustive, same scope as
# `subtitle_discovery/language_codes.py`. No `pt-br` entry: see the class docstring's
# "Known gap" for why Brazilian Portuguese can't be reliably distinguished here.
_ANIMETOSHO_LANGUAGE_CODES: dict[str, str] = {
    "ar": "ara",
    "en": "eng",
    "fi": "fin",
    "fr": "fra",
    "de": "deu",
    "he": "heb",
    "id": "ind",
    "it": "ita",
    "ja": "jpn",
    "pt": "por",
    "pl": "pol",
    "ru": "rus",
    "es": "spa",
    "sv": "swe",
    "th": "tha",
    "tr": "tur",
    "vi": "vie",
}

# Process-lifetime, in-memory caches/quota — not persisted, reset on restart. legendarr
# has neither `lxml` nor `dogpile.cache` (what Bazarr's own `anidb.py` uses); one
# long-running process makes a restart-resets counter an acceptable simplification.
_mapping_cache_root: ET.Element | None = None
_mapping_cache_fetched_at = 0.0
_episodes_cache: dict[int, tuple[float, ET.Element]] = {}
_daily_quota_date: date | None = None
_daily_quota_count = 0


class AnimeToshoProvider:
    """Real Anime Tosho `search()`/`download()` backend, ported from Bazarr's own
    `AnimeToshoProvider` (`/home/viudes/projects/bazarr/custom_libs/subliminal_patch/
    providers/animetosho.py`), the confirmed-working reference. Anime Tosho's own feed
    API (`feed.animetosho.org/json`) has no text search at all, only `?eid=<AniDB
    episode id>`, so resolving that id is most of this module:

    1. `Series.tvdb_id`/`season`/`episode` -> `(AniDB anime id, AniDB episode number)`,
       via the same community-maintained TVDB->AniDB mapping list Bazarr's
       `bazarr/subtitles/refiners/anidb.py:AniDBClient.get_show_information` uses
       (`_resolve_anidb_ids`).
    2. `(AniDB anime id, AniDB episode number)` -> AniDB episode id, via a real call to
       the AniDB HTTP API — needs a registered AniDB API client key
       (`SubtitleProviderConfig.api_key`, this kind's only credential), and is
       rate-limited to Bazarr's own 200-requests/day soft limit, tracked here as a
       simple in-memory daily counter (`_daily_quota_date`/`_daily_quota_count`) rather
       than a persistent cache.
    3. Only then: `eid=` -> torrent entries -> per-torrent file attachments -> download.

    Series only, like `TVsubtitlesProvider` — Anime Tosho has no movie content, so a
    search missing any of `tvdb_id`/`season`/`episode` is skipped with no HTTP calls.
    `imdb_id`/`moviehash`/`video_path` are ignored — not used here.

    Known gap (deferred): Bazarr disambiguates Brazilian Portuguese from plain
    Portuguese via an attachment `name` field its own reference reads inconsistently
    (a `str.find()` result used as a truthy check, which is backwards — `-1`, "not
    found", is truthy) and that isn't even present on a real subtitle attachment's
    `info` object (confirmed against the fixture data in
    `bazarr/tests/subliminal_patch/data/animetosho_series_response.json`). There's no
    reliable signal for this distinction in Anime Tosho's own API, so this provider only
    ever matches plain `pt` — a `pt-br` search against Anime Tosho always comes back
    empty rather than risk a wrong-region match.

    No session/login to hold — one short-lived `ProviderHttpClient` per call, same as
    `SubdlProvider`/`SubsourceProvider`. Downloads are `.xz`-compressed (`lzma`), not
    zipped like every other provider here.
    """

    name = "animetosho"

    def __init__(self, config: SubtitleProviderConfig) -> None:
        self._anidb_api_key = config.api_key

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
        """See the class docstring for why `tvdb_id`/`season`/`episode` are all
        required — unlike every other provider here, there's no title-only fallback.
        `imdb_id`/`moviehash`/`video_path` are ignored."""
        if tvdb_id is None or season is None or episode is None:
            logger.debug(
                "animetosho search skipped for %r: no tvdb_id/season/episode resolved", title
            )
            return []
        language_code = _ANIMETOSHO_LANGUAGE_CODES.get(language.strip().lower())
        if language_code is None or not self._anidb_api_key:
            return []
        assert self._anidb_api_key is not None
        client = ProviderHttpClient("Anime Tosho", ANIMETOSHO_FEED_BASE_URL)
        try:
            mapping_root = _get_anime_list_mapping(client)
            anidb_ids = _resolve_anidb_ids(mapping_root, tvdb_id, season, episode)
            if anidb_ids is None:
                logger.debug(
                    "animetosho search skipped for %r: no AniDB mapping for tvdb id %d",
                    title,
                    tvdb_id,
                )
                return []
            anidb_id, anidb_episode_no = anidb_ids
            episode_id = _resolve_anidb_episode_id(
                client, self._anidb_api_key, anidb_id, anidb_episode_no
            )
            if episode_id is None:
                return []
            return [
                result
                for entry in _fetch_feed_entries(client, episode_id)
                for result in _search_entry_subtitles(client, entry, language, language_code)
            ]
        finally:
            client.close()

    def download(self, result: SubtitleSearchResult) -> str:
        subtitle_id = int(result.download_id)
        hex_id = format(subtitle_id, "08x")
        client = ProviderHttpClient("Anime Tosho", ANIMETOSHO_STORAGE_BASE_URL)
        try:
            response = client.request("GET", f"/storage/attach/{hex_id}/{subtitle_id}.xz")
            if not response.is_success:
                raise ProviderClientError(
                    f"Anime Tosho download for attachment {subtitle_id} failed with "
                    f"{response.status_code}"
                )
        finally:
            client.close()
        return _extract_subtitle_text(response.content)


def _get_anime_list_mapping(client: ProviderHttpClient) -> ET.Element:
    """The community-maintained TVDB->AniDB mapping list, cached for a day at a time —
    ported from Bazarr's own `AniDBClient.get_series_mappings` (`anidb.py:61-69`)."""
    global _mapping_cache_root, _mapping_cache_fetched_at
    if (
        _mapping_cache_root is not None
        and time.time() - _mapping_cache_fetched_at < _MAPPING_CACHE_TTL_SECONDS
    ):
        return _mapping_cache_root
    response = client.request("GET", _ANIME_LIST_MAPPING_URL)
    if not response.is_success:
        raise ProviderClientError(
            f"Anime Tosho TVDB-AniDB mapping fetch failed with {response.status_code}"
        )
    root = ET.fromstring(response.content)
    _mapping_cache_root = root
    _mapping_cache_fetched_at = time.time()
    return root


def _resolve_anidb_ids(
    root: ET.Element, tvdb_id: int, season: int, episode: int
) -> tuple[int, int] | None:
    """Turn (TVDB series id, season, episode) into (AniDB anime id, AniDB episode no).
    Ported from Bazarr's `AniDBClient.get_show_information` (`anidb.py:72-141`,
    confirmed-working reference) — same season-offset arithmetic, and the same
    `mapping-list` override some franchises need when TVDB and AniDB don't number
    episodes the same way within a season."""
    animes = sorted(
        (
            (anime, int(anime.attrib.get("episodeoffset", 0)))
            for anime in root.findall(
                f".//anime[@tvdbid='{tvdb_id}'][@defaulttvdbseason='{season}']"
            )
        ),
        key=lambda item: item[1],
    )
    anidb_id: int | None = None
    offset = 0
    if animes:
        for anime, episode_offset in animes:
            mapped_episode = _resolve_mapping_list_override(anime, episode)
            if mapped_episode is not None:
                return int(anime.attrib["anidbid"]), mapped_episode
            if episode > episode_offset:
                anidb_id = int(anime.attrib["anidbid"])
                offset = episode_offset
    else:
        # Some entries store every TVDB season under one AniDB id via an explicit
        # per-season <mapping>, flagged by defaulttvdbseason="a" instead of a real
        # season number.
        query = f".//anime[@tvdbid='{tvdb_id}'][@defaulttvdbseason='a']"
        for special_entry in root.findall(query):
            season_mapping = special_entry.find(f".//mapping[@tvdbseason='{season}']")
            offset = (
                int(season_mapping.attrib.get("offset", 0)) if season_mapping is not None else 0
            )
            anidb_id = int(special_entry.attrib["anidbid"])
    if anidb_id is None:
        return None
    return anidb_id, episode - offset


def _resolve_mapping_list_override(anime: ET.Element, episode: int) -> int | None:
    """A `mapping-list` on an `<anime>` entry lists exact TVDB->AniDB episode overrides
    (e.g. `;1-1;2-1;3-1;`, one AniDB episode possibly covering several TVDB ones) for
    episodes that don't follow the season's flat offset — checked before the offset
    math in `_resolve_anidb_ids`."""
    mapping_list = anime.find("mapping-list")
    if mapping_list is None:
        return None
    for mapping in mapping_list.findall("mapping"):
        if not mapping.text:
            continue
        for episode_ref in mapping.text.split(";"):
            if not episode_ref or "-" not in episode_ref:
                continue
            anidb_episode_text, tvdb_part = episode_ref.split("-", 1)
            tvdb_episodes = tvdb_part.split("+") if "+" in tvdb_part else [tvdb_part]
            if any(int(tvdb_episode) == episode for tvdb_episode in tvdb_episodes):
                return int(anidb_episode_text)
    return None


def _quota_available() -> bool:
    global _daily_quota_date, _daily_quota_count
    today = date.today()
    if _daily_quota_date != today:
        _daily_quota_date = today
        _daily_quota_count = 0
    return _daily_quota_count < _DAILY_QUOTA_LIMIT


def _get_anidb_episodes(
    client: ProviderHttpClient, api_key: str, anidb_id: int
) -> ET.Element | None:
    """The full episode list for one AniDB anime id, cached a day at a time per id —
    ported from Bazarr's `AniDBClient.get_episodes` (`anidb.py:157-189`), including its
    daily quota check and the two AniDB response codes it treats as fatal (500 = API
    abuse ban, 302 = the client key is disabled/unregistered)."""
    global _daily_quota_count
    cached = _episodes_cache.get(anidb_id)
    if cached is not None and time.time() - cached[0] < _EPISODES_CACHE_TTL_SECONDS:
        return cached[1]
    if not _quota_available():
        logger.warning(
            "animetosho AniDB episode lookup skipped: daily quota of %d requests reached",
            _DAILY_QUOTA_LIMIT,
        )
        return None
    params: dict[str, Any] = {
        "request": "anime",
        "client": api_key,
        "clientver": ANIDB_CLIENT_VERSION,
        "protover": 1,
        "aid": anidb_id,
    }
    response = client.request("GET", f"{ANIDB_API_URL}?{urlencode(params)}")
    if not response.is_success:
        raise ProviderClientError(
            f"AniDB API request for anime {anidb_id} failed with {response.status_code}"
        )
    _daily_quota_count += 1
    root = ET.fromstring(response.content)
    if root.attrib.get("code") in {"500", "302"}:
        raise ProviderClientError("AniDB API rejected the client key or banned this client")
    episodes = root.find("episodes")
    if episodes is None:
        return None
    _episodes_cache[anidb_id] = (time.time(), episodes)
    return episodes


def _resolve_anidb_episode_id(
    client: ProviderHttpClient, api_key: str, anidb_id: int, anidb_episode_no: int
) -> int | None:
    episodes = _get_anidb_episodes(client, api_key, anidb_id)
    if episodes is None:
        return None
    episode_element = episodes.find(f".//episode[epno='{anidb_episode_no}']")
    if episode_element is None:
        return None
    episode_id = episode_element.attrib.get("id")
    return int(episode_id) if episode_id is not None else None


def _fetch_feed_entries(client: ProviderHttpClient, episode_id: int) -> list[dict[str, Any]]:
    response = client.get_json(f"/json?eid={episode_id}")
    if not isinstance(response, list):
        return []
    complete = [entry for entry in response if entry.get("status") == "complete"]
    complete.sort(key=lambda entry: entry.get("timestamp", 0), reverse=True)
    return complete[:_ENTRY_LIMIT]


def _search_entry_subtitles(
    client: ProviderHttpClient, entry: dict[str, Any], language: str, language_code: str
) -> list[SubtitleSearchResult]:
    entry_id = entry.get("id")
    if entry_id is None:
        return []
    response = client.get_json(f"/json?show=torrent&id={entry_id}")
    if not isinstance(response, dict):
        return []
    release_name = response.get("title") or entry.get("title") or "Anime Tosho"
    return [
        result
        for file in response.get("files", [])
        for attachment in file.get("attachments", [])
        if (result := _parse_subtitle_attachment(attachment, release_name, language, language_code))
        is not None
    ]


def _parse_subtitle_attachment(
    attachment: dict[str, Any], release_name: str, language: str, language_code: str
) -> SubtitleSearchResult | None:
    if attachment.get("type") != "subtitle":
        return None
    info = attachment.get("info") or {}
    # A missing language tag defaults to English, same fallback Anime Tosho's own site
    # assumes (ported from Bazarr's `AnimeToshoProvider._get_series`).
    if (info.get("lang") or "eng") != language_code:
        return None
    attachment_id = attachment.get("id")
    if attachment_id is None:
        return None
    return SubtitleSearchResult(
        release_name=release_name,
        download_id=str(attachment_id),
        language=language,
    )


def _extract_subtitle_text(content: bytes) -> str:
    if not content.startswith(_XZ_MAGIC):
        raise ProviderClientError("Anime Tosho download wasn't a valid .xz archive")
    return lzma.decompress(content).decode("utf-8", errors="replace")
