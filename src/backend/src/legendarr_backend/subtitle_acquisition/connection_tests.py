"""Per-provider "test connection" checks for `SubtitleProviderConfig`.

This is deliberately *not* the (still-deferred) `SubtitleProvider` protocol — each function
here only answers "is this reachable/authenticated," not "find and download a subtitle."
Endpoints below were confirmed either against each provider's official API docs or, where no
official API exists, against Bazarr's own working provider integrations
(`/home/viudes/projects/bazarr`, read-only reference).
"""

import xml.etree.ElementTree as ET
from urllib.parse import urlencode

from legendarr_backend.http_client.client import (
    ProviderClientError,
    ProviderHttpClient,
    describe_error,
)
from legendarr_backend.subtitle_acquisition.models import SubtitleProviderConfig
from legendarr_backend.subtitle_acquisition.providers.addic7ed import (
    ADDIC7ED_BASE_URL,
    addic7ed_login,
)
from legendarr_backend.subtitle_acquisition.providers.animetosho import (
    ANIDB_API_URL,
    ANIDB_CLIENT_VERSION,
    ANIMETOSHO_FEED_BASE_URL,
)
from legendarr_backend.subtitle_acquisition.providers.legendas_net import (
    LEGENDAS_NET_API_BASE_URL,
    legendas_net_login,
)
from legendarr_backend.subtitle_acquisition.providers.opensubtitles import (
    opensubtitles_client,
    opensubtitles_login,
)
from legendarr_backend.subtitle_acquisition.providers.subsource import SUBSOURCE_API_BASE_URL

ConnectionTestResult = tuple[bool, str]


def test_connection(config: SubtitleProviderConfig) -> ConnectionTestResult:
    """Dispatch to the connection check for `config.kind`. Returns `(success, message)`,
    the same shape as `arr_services/router.py`'s `_probe_connection`."""
    tester = _TESTERS.get(config.kind)
    if tester is None:
        return False, f"Unknown provider kind: {config.kind}"
    return tester(config)


def _require(value: str | None, label: str) -> str | None:
    if not value:
        return f"{label} is required"
    return None


def _test_opensubtitles(config: SubtitleProviderConfig) -> ConnectionTestResult:
    if (error := _require(config.username, "Username")) is not None:
        return False, error
    if (error := _require(config.password, "Password")) is not None:
        return False, error
    assert config.username is not None
    assert config.password is not None
    # `opensubtitles_login` is the same login flow the real provider uses once
    # credentials pass. The `Api-Key` header it needs identifies legendarr itself, not
    # the user (see `providers/opensubtitles.py`'s module docstring), so it's baked into
    # `opensubtitles_client()` rather than coming from `config`.
    client = opensubtitles_client()
    try:
        opensubtitles_login(client, config.username, config.password)
    except ProviderClientError as exc:
        return False, str(exc)
    finally:
        client.close()
    return True, "Connection successful"


def _test_subdl(config: SubtitleProviderConfig) -> ConnectionTestResult:
    if (error := _require(config.api_key, "An API Key")) is not None:
        return False, error
    client = ProviderHttpClient("Subdl", "https://api.subdl.com")
    try:
        # Subdl has no dedicated "ping" route — the smallest documented call is a search
        # with a fixed query, per https://subdl.com/api-doc.
        body = client.get_json(f"/api/v1/subtitles?api_key={config.api_key}&film_name=test")
    except ProviderClientError as exc:
        return False, describe_error(exc)
    finally:
        client.close()
    if isinstance(body, dict) and body.get("status") is False:
        return False, body.get("error") or "The server rejected the API Key"
    return True, "Connection successful"


def _test_subsource(config: SubtitleProviderConfig) -> ConnectionTestResult:
    if (error := _require(config.api_key, "An API Key")) is not None:
        return False, error
    assert config.api_key is not None
    # Same real API `providers/subsource.py`'s `search()` calls, confirmed against
    # Bazarr's own working `SubsourceProvider` (see that module's docstring) — a smallest
    # documented call (`GET /movies/search`) with a fixed query, same shape `_test_subdl`
    # uses since this API has no dedicated "ping" route either.
    client = ProviderHttpClient("Subsource", SUBSOURCE_API_BASE_URL)
    try:
        client.get_json(f"/movies/search?api_key={config.api_key}&searchType=text&q=test")
    except ProviderClientError as exc:
        return False, describe_error(exc)
    finally:
        client.close()
    return True, "Connection successful"


def _test_legendas_net(config: SubtitleProviderConfig) -> ConnectionTestResult:
    if (error := _require(config.username, "Email")) is not None:
        return False, error
    if (error := _require(config.password, "Password")) is not None:
        return False, error
    assert config.username is not None
    assert config.password is not None
    # `legendas_net_login` is the same login flow the real provider uses once
    # credentials pass.
    client = ProviderHttpClient("legendas.net", LEGENDAS_NET_API_BASE_URL)
    try:
        legendas_net_login(client, config.username, config.password)
    except ProviderClientError as exc:
        return False, str(exc)
    finally:
        client.close()
    return True, "Connection successful"


def _test_addic7ed(config: SubtitleProviderConfig) -> ConnectionTestResult:
    if (error := _require(config.username, "Username")) is not None:
        return False, error
    if (error := _require(config.password, "Password")) is not None:
        return False, error
    assert config.username is not None
    assert config.password is not None
    # No official API and no JSON responses — Addic7ed's login is an HTML form that can be
    # gated behind a reCAPTCHA (see Bazarr's addic7ed.py), which can't be solved here.
    # `addic7ed_login` is the same login flow the real provider uses once credentials pass.
    client = ProviderHttpClient("Addic7ed", ADDIC7ED_BASE_URL)
    try:
        addic7ed_login(client, config.username, config.password)
    except ProviderClientError as exc:
        return False, str(exc)
    finally:
        client.close()
    return True, "Connection successful"


def _test_betaseries(config: SubtitleProviderConfig) -> ConnectionTestResult:
    if (error := _require(config.api_key, "An API Token")) is not None:
        return False, error
    # BetaSeries has no dedicated "validate token" route either — this mirrors Bazarr's own
    # betaseries.py:72-119: a real search call, reading `errors[0]['code']` on a 400 response
    # (1001 = invalid token, 4001 = token fine but no matching series — a deliberately-bogus
    # `thetvdb_id` guarantees the latter on a good token, never a real result to parse).
    client = ProviderHttpClient("BetaSeries", "https://api.betaseries.com")
    try:
        response = client.request("GET", f"/episodes/display?key={config.api_key}&thetvdb_id=0")
    except ProviderClientError as exc:
        return False, describe_error(exc)
    finally:
        client.close()
    if response.status_code == 400:
        errors = response.json().get("errors") or []
        if errors and errors[0].get("code") == 1001:
            return False, "The server rejected the API Token — check that it's correct"
    return True, "Connection successful"


def _test_yify_subtitles(config: SubtitleProviderConfig) -> ConnectionTestResult:
    return _reachability_only("YIFY Subtitles", "https://yifysubtitles.ch")


def _test_tvsubtitles(config: SubtitleProviderConfig) -> ConnectionTestResult:
    return _reachability_only("TVsubtitles", "http://www.tvsubtitles.net")


def _test_napiprojekt(config: SubtitleProviderConfig) -> ConnectionTestResult:
    return _reachability_only("Napiprojekt", "https://www.napiprojekt.pl")


def _test_animetosho(config: SubtitleProviderConfig) -> ConnectionTestResult:
    if (error := _require(config.api_key, "An AniDB API Client Key")) is not None:
        return False, error
    assert config.api_key is not None
    # Same real AniDB HTTP API `providers/animetosho.py`'s `_get_anidb_episodes` calls,
    # confirmed against Bazarr's own working `AniDBClient.get_episodes` (see that
    # module's docstring) — a fixed, long-registered anime id (AniDB has no dedicated
    # "ping" route, and every real call costs against the same daily quota either way).
    params = {
        "request": "anime",
        "client": config.api_key,
        "clientver": ANIDB_CLIENT_VERSION,
        "protover": 1,
        "aid": 1,
    }
    client = ProviderHttpClient("Anime Tosho", ANIMETOSHO_FEED_BASE_URL)
    try:
        response = client.request("GET", f"{ANIDB_API_URL}?{urlencode(params)}")
    except ProviderClientError as exc:
        return False, describe_error(exc)
    finally:
        client.close()
    if not response.is_success:
        return False, f"AniDB API request failed with {response.status_code}"
    code = ET.fromstring(response.content).attrib.get("code")
    if code in {"500", "302"}:
        return False, "The server rejected the AniDB API Client Key — check that it's correct"
    return True, "Connection successful"


def _test_supersubtitles(config: SubtitleProviderConfig) -> ConnectionTestResult:
    return _reachability_only("Supersubtitles", "https://www.feliratok.eu")


def _test_animekalesi(config: SubtitleProviderConfig) -> ConnectionTestResult:
    return _reachability_only("AnimeKalesi", "https://www.animekalesi.com")


def _test_greeksubtitles(config: SubtitleProviderConfig) -> ConnectionTestResult:
    return _reachability_only("GreekSubtitles", "http://gr.greek-subtitles.com")


def _reachability_only(name: str, base_url: str) -> ConnectionTestResult:
    """No credential exists for this provider — the "test" only proves the site answers."""
    client = ProviderHttpClient(name, base_url)
    try:
        client.ping("/")
    except ProviderClientError as exc:
        # Not describe_error(exc) — that assumes a 401/403 means a rejected API Key, which
        # doesn't apply here: these providers have no credential at all.
        return False, str(exc)
    finally:
        client.close()
    return True, "Site is reachable (no credential to validate for this provider)"


_TESTERS = {
    "opensubtitles": _test_opensubtitles,
    "addic7ed": _test_addic7ed,
    "yify_subtitles": _test_yify_subtitles,
    "subdl": _test_subdl,
    "tvsubtitles": _test_tvsubtitles,
    "legendas_net": _test_legendas_net,
    "napiprojekt": _test_napiprojekt,
    "subsource": _test_subsource,
    "animetosho": _test_animetosho,
    "supersubtitles": _test_supersubtitles,
    "animekalesi": _test_animekalesi,
    "greeksubtitles": _test_greeksubtitles,
    "betaseries": _test_betaseries,
}
