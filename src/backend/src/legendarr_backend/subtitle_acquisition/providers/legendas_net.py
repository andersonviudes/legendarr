import io
import logging
from pathlib import Path
from typing import Any
from urllib.parse import urljoin
from zipfile import ZipFile, is_zipfile

from legendarr_backend.http_client.client import ProviderClientError, ProviderHttpClient
from legendarr_backend.subtitle_acquisition.models import SubtitleProviderConfig
from legendarr_backend.subtitle_acquisition.providers.base import SubtitleSearchResult

logger = logging.getLogger(__name__)

# Same constants `connection_tests.py`'s "Test connection" check uses — owned here since
# this is now the module that does the real, ongoing calling. The API lives on a
# different host path (`/api`) than the download links its search results return
# (bare `legendas.net`), so both are kept, not just one base URL.
LEGENDAS_NET_API_BASE_URL = "https://legendas.net/api"
LEGENDAS_NET_SITE_BASE_URL = "https://legendas.net"


class LegendasNetProvider:
    """Real legendas.net `search()`/`download()` backend, ported from Bazarr's own
    `LegendasNetProvider` (`/home/viudes/projects/bazarr/custom_libs/subliminal_patch/
    providers/legendasnet.py`), the confirmed-working reference for this JSON API — no
    public docs exist for it otherwise.

    Brazilian Portuguese only — the site's own `languages = {Language('por', 'BR')}`
    (`legendasnet.py:86`), so a search for any other language is skipped with no HTTP
    calls. Unlike every other provider so far, legendas.net has both movie and TV
    content with real per-episode search: `season`/`episode` set means a TV search,
    otherwise an `imdb_id` (the orchestrator's own movie signal,
    `acquire_media_file_subtitle.py:84`) means a movie search; neither means this is a
    series file with no resolved episode, which is skipped the same way TVsubtitles
    skips one.

    Like `Addic7edProvider`, this holds one lazily-created, logged-in
    `ProviderHttpClient` for the provider instance's lifetime — `close()` releases it.
    Unlike Addic7ed's cookie session, auth here is a bearer token attached per call
    (`_auth_headers`), since the token also has to reach `download()`'s separate,
    non-`/api` host.
    """

    name = "legendas_net"

    def __init__(self, config: SubtitleProviderConfig) -> None:
        self._username = config.username
        self._password = config.password
        self._client: ProviderHttpClient | None = None
        self._access_token: str | None = None

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
        """`moviehash`/`series_imdb_id` are ignored — not used here. See the class
        docstring for how `imdb_id`/`season`/`episode` pick a movie search, a TV
        search, or a skip. `video_path` is ignored too."""
        if language.strip().lower() != "pt-br":
            return []
        if season is not None and episode is not None:
            endpoint = "/v1/search/tv"
            page_prefix = "tv_legenda"
            result_key = "tv_shows"
            payload: dict[str, Any] = {
                "name": title,
                "page": 1,
                "per_page": 25,
                "tv_season": season,
                "tv_episode": episode,
            }
        elif imdb_id is not None:
            endpoint = "/v1/search/movie"
            page_prefix = "legenda"
            result_key = "movies"
            payload = {"name": title, "page": 1, "per_page": 25, "imdb_id": imdb_id}
        else:
            logger.debug(
                "legendas_net search skipped for %r: no movie imdb_id or resolved series episode",
                title,
            )
            return []

        client = self._authenticated_client()
        response = client.request("GET", endpoint, json=payload, headers=self._auth_headers())
        if not response.is_success:
            raise ProviderClientError(
                f"legendas.net search for {title!r} failed with {response.status_code}"
            )
        body = response.json()
        if (
            not isinstance(body, dict)
            or not body.get("success", True)
            or not body.get("status", True)
        ):
            return []
        return [
            result
            for item in body.get(result_key, [])
            if (result := _parse_result(item, title, page_prefix)) is not None
        ]

    def download(self, result: SubtitleSearchResult) -> str:
        client = self._authenticated_client()
        download_url = urljoin(LEGENDAS_NET_SITE_BASE_URL, result.download_id)
        response = client.request("GET", download_url, headers=self._auth_headers())
        if not response.is_success:
            raise ProviderClientError(
                f"legendas.net download {download_url} failed with {response.status_code}"
            )
        return _extract_subtitle_text(response.content)

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None
            self._access_token = None

    def _authenticated_client(self) -> ProviderHttpClient:
        if self._client is None:
            # Only ever constructed via `resolve_subtitle_provider_chain`, which
            # already filtered to configs with `has_credentials` true for this kind —
            # both fields are guaranteed set here.
            assert self._username is not None
            assert self._password is not None
            client = ProviderHttpClient("legendas.net", LEGENDAS_NET_API_BASE_URL)
            self._access_token = legendas_net_login(client, self._username, self._password)
            self._client = client
        return self._client

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._access_token}"}


def legendas_net_login(client: ProviderHttpClient, username: str, password: str) -> str:
    """POST `/v1/login` (email + password) -> access token, the confirmed-working flow
    from Bazarr's own `LegendasNetProvider.login` (`legendasnet.py:99-124`). Raises
    instead of returning `None` on a missing token, so a `search()`/`download()`
    caller's broad `except Exception` (`acquire_media_file_subtitle.py`) treats a login
    failure as "this provider isn't usable right now" and moves to the next one.
    Shared with `connection_tests._test_legendas_net`, which is the same flow with no
    real request to follow it.
    """
    body = client.post_json("/v1/login", {"email": username, "password": password})
    access_token = body.get("access_token") if isinstance(body, dict) else None
    if not access_token:
        raise ProviderClientError("legendas.net login succeeded but no access token was returned")
    return access_token


def _parse_result(
    item: dict[str, Any], fallback_release_name: str, page_prefix: str
) -> SubtitleSearchResult | None:
    path = item.get("path")
    item_id = item.get("id")
    if not isinstance(path, str) or item_id is None:
        return None
    tmdb_id = item.get("tmdb_id")
    page_link = (
        f"{LEGENDAS_NET_SITE_BASE_URL}/{page_prefix}?movie_id={tmdb_id}&legenda_id={item_id}"
        if tmdb_id is not None
        else None
    )
    return SubtitleSearchResult(
        release_name=item.get("release_name") or fallback_release_name,
        download_id=path,
        language="pt-BR",
        page_link=page_link,
    )


def _extract_subtitle_text(content: bytes) -> str:
    stream = io.BytesIO(content)
    if not is_zipfile(stream):
        # Unlike the other zip-only providers, legendas.net doesn't always zip its
        # download — Bazarr's own `download_subtitle` (`legendasnet.py:250-260`) falls
        # back to the raw response body as the subtitle text itself.
        return content.decode("utf-8", errors="replace")
    with ZipFile(stream) as archive:
        for name in archive.namelist():
            if name.lower().endswith((".srt", ".sub")):
                return archive.read(name).decode("utf-8", errors="replace")
    raise ProviderClientError("legendas.net archive contained no .srt/.sub file")
