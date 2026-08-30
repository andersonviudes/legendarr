from pathlib import Path
from urllib.parse import urlencode

from legendarr_backend.http_client.client import ProviderClientError, ProviderHttpClient
from legendarr_backend.subtitle_acquisition.models import SubtitleProviderConfig
from legendarr_backend.subtitle_acquisition.providers.base import SubtitleSearchResult

# Same constant `connection_tests.py`'s "Test connection" check uses — owned here since
# this is now the module that does the real, ongoing calling.
OPENSUBTITLES_USER_AGENT = "legendarr (+https://andersonviudes.github.io/legendarr)"

OPENSUBTITLES_BASE_URL = "https://api.opensubtitles.com"

# legendarr's own OpenSubtitles.com API consumer key, registered at
# https://www.opensubtitles.com/en/consumers under the legendarr application. This
# identifies legendarr as the calling application — the same app-level credential Bazarr
# hardcodes for every one of its own users (`bazarr/app/get_providers.py:261`,
# `'s38zmzVlW7IlYruWi7mHwDYl2SfMQoC1'`). It's never the end user's own secret, which is
# why it's a module constant here instead of a per-`SubtitleProviderConfig` field like
# the other API-key kinds — the user only ever provides their own OpenSubtitles.com
# username/password (see `SubtitleProviderConfig._USERNAME_PASSWORD_KINDS`).
_APP_API_KEY = "s57fpg9JaLZqnSZCAAF8kz43DeDI4AOK"


def opensubtitles_client(
    base_url: str = OPENSUBTITLES_BASE_URL, *, token: str | None = None
) -> ProviderHttpClient:
    """Build a `ProviderHttpClient` carrying the header(s) every OpenSubtitles.com
    request needs — shared by this module's own login step and
    `connection_tests._test_opensubtitles`. `Api-Key` (see `_APP_API_KEY` above) is
    always sent; `Authorization` is only added once a user's logged in
    (`opensubtitles_login`)."""
    headers = {"Api-Key": _APP_API_KEY, "User-Agent": OPENSUBTITLES_USER_AGENT}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return ProviderHttpClient("OpenSubtitles", base_url, headers=headers)


def opensubtitles_login(
    client: ProviderHttpClient, username: str, password: str
) -> tuple[str, str | None]:
    """POST `/api/v1/login` (username + password) -> `(token, base_url)`. Raises instead
    of returning an empty token, so a `search()`/`download()` caller's broad exception
    handling treats a login failure as "this provider isn't usable right now" and moves
    on to the next one. Ported from Bazarr's own `OpenSubtitlesComProvider.login`
    (`opensubtitlescom.py:214-243`, the confirmed-working reference) — `base_url` comes
    back non-default (`vip-...`) for a VIP account, which `_authenticated_client` uses to
    route that account's calls to OpenSubtitles' own dedicated VIP host. Shared with
    `connection_tests._test_opensubtitles`, which is the same flow with no real request
    to follow it.
    """
    body = client.post_json("/api/v1/login", {"username": username, "password": password})
    token = body.get("token") if isinstance(body, dict) else None
    if not token:
        raise ProviderClientError("OpenSubtitles login succeeded but no token was returned")
    return token, body.get("base_url") if isinstance(body, dict) else None


class OpenSubtitlesProvider:
    """Real OpenSubtitles `search()`/`download()` backend, built from a
    `SubtitleProviderConfig`. `include_ai_translated`/`include_machine_translated` map
    directly onto the API's own `ai_translated`/`machine_translated` filters — the first
    fields on that config this provider actually reads.

    Like `LegendasNetProvider`, this holds one lazily-created, logged-in
    `ProviderHttpClient` for the provider instance's lifetime — `close()` releases it.
    Unlike legendas.net (whose download host differs from its API host, so auth travels
    per-call), OpenSubtitles' `Authorization` is baked into the client at construction —
    every call this provider makes, including the download link fetch, goes through the
    one client.
    """

    name = "opensubtitles"

    def __init__(self, config: SubtitleProviderConfig) -> None:
        self._username = config.username
        self._password = config.password
        self._include_ai_translated = config.include_ai_translated
        self._include_machine_translated = config.include_machine_translated
        self._use_hash = config.use_hash
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
        series_imdb_id: str | None = None,
    ) -> list[SubtitleSearchResult]:
        """`moviehash` is only ever sent when this provider's own `use_hash` config is
        on — the caller always offers it when it has one, this is where that setting
        actually takes effect.

        `season`/`episode` set together anchor the search on one episode. With
        `series_imdb_id` also given, the API is asked for that episode precisely —
        `parent_imdb_id`/`season_number`/`episode_number`, no `query` — since
        OpenSubtitles' own guidance is that combining an id-based lookup with a text
        query produces conflicting filters. `series_imdb_id` unresolved falls back to
        `query`/`season_number`/`episode_number` together, still narrower than title
        alone. Movie search (`season`/`episode` both `None`) is unchanged: `query` plus
        `imdb_id` when given. `video_path`/`tvdb_id` are ignored — not used here."""
        params: dict[str, str | int] = {
            "languages": language.lower(),
            "ai_translated": "include" if self._include_ai_translated else "exclude",
            "machine_translated": "include" if self._include_machine_translated else "exclude",
        }
        if season is not None and episode is not None:
            if series_imdb_id:
                params["parent_imdb_id"] = series_imdb_id.removeprefix("tt")
            else:
                params["query"] = title
            params["season_number"] = season
            params["episode_number"] = episode
        else:
            params["query"] = title
            if imdb_id:
                params["imdb_id"] = imdb_id.removeprefix("tt")
        if moviehash and self._use_hash:
            params["moviehash"] = moviehash
        client = self._authenticated_client()
        response = client.get_json(f"/api/v1/subtitles?{urlencode(params)}")
        return [
            SubtitleSearchResult(
                release_name=attributes.get("release") or title,
                download_id=str(file["file_id"]),
                language=attributes.get("language", language),
                hash_matched=bool(attributes.get("moviehash_match", False)),
                hearing_impaired=bool(attributes.get("hearing_impaired", False)),
                uploader=attributes.get("uploader", {}).get("name") or None,
            )
            for entry in response.get("data", [])
            for attributes in [entry["attributes"]]
            for file in attributes.get("files", [])
        ]

    def download(self, result: SubtitleSearchResult) -> str:
        client = self._authenticated_client()
        download_info = client.post_json("/api/v1/download", {"file_id": int(result.download_id)})
        response = client.request("GET", download_info["link"], follow_redirects=True)
        if not response.is_success:
            raise ProviderClientError(
                f"OpenSubtitles download link {download_info['link']} failed with "
                f"{response.status_code}"
            )
        return response.text

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def _authenticated_client(self) -> ProviderHttpClient:
        if self._client is None:
            # Only ever constructed via `resolve_subtitle_provider_chain`, which already
            # filtered to configs with `has_credentials` true for this kind — both
            # fields are guaranteed set here.
            assert self._username is not None
            assert self._password is not None
            client = opensubtitles_client()
            token, base_url = opensubtitles_login(client, self._username, self._password)
            if base_url and base_url.startswith("vip"):
                client.close()
                client = opensubtitles_client(f"https://{base_url}", token=token)
            self._client = client
        return self._client
