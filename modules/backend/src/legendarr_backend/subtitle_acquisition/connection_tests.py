"""Per-provider "test connection" checks for `SubtitleProviderConfig`.

This is deliberately *not* the (still-deferred) `SubtitleProvider` protocol — each function
here only answers "is this reachable/authenticated," not "find and download a subtitle."
Endpoints below were confirmed either against each provider's official API docs or, where no
official API exists, against Bazarr's own working provider integrations
(`/home/viudes/projects/bazarr`, read-only reference).
"""

from legendarr_backend.http_client.client import (
    ProviderClientError,
    ProviderHttpClient,
    describe_error,
)
from legendarr_backend.subtitle_acquisition.models import SubtitleProviderConfig

ConnectionTestResult = tuple[bool, str]

_OPENSUBTITLES_USER_AGENT = "legendarr (+https://andersonviudes.github.io/legendarr)"


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
    if (error := _require(config.api_key, "An API Key")) is not None:
        return False, error
    client = ProviderHttpClient(
        "OpenSubtitles",
        "https://api.opensubtitles.com",
        headers={"Api-Key": config.api_key, "User-Agent": _OPENSUBTITLES_USER_AGENT},
    )
    try:
        client.get_json("/api/v1/infos/user")
    except ProviderClientError as exc:
        return False, describe_error(exc)
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
    # Subsource's docs page (subsource.net/api-docs) is Cloudflare-protected and couldn't be
    # confirmed during implementation, so this only checks the site is reachable, not that
    # the API Key itself is valid — narrower than the other API-key providers above.
    # Lead for whoever revisits this with a real key to test: third-party clients
    # (github.com/awpetrik/SubDL, github.com/quekky/subsource-dl) reverse-engineered
    # `https://api.subsource.net` with an `X-API-Key` header, and `POST /api/searchMovie`
    # returns "API key invalid or expired" on a bad key — but one of those clients hits the
    # same API with no key at all, so it's unconfirmed whether that endpoint actually
    # enforces the key. Not wired in here without a real key to verify it against.
    client = ProviderHttpClient("Subsource", "https://subsource.net")
    try:
        client.ping("/")
    except ProviderClientError as exc:
        return False, describe_error(exc)
    finally:
        client.close()
    return True, "Site is reachable — the API Key itself isn't validated yet"


def _test_legendas_net(config: SubtitleProviderConfig) -> ConnectionTestResult:
    if (error := _require(config.username, "Email")) is not None:
        return False, error
    if (error := _require(config.password, "Password")) is not None:
        return False, error
    client = ProviderHttpClient("legendas.net", "https://legendas.net/api")
    try:
        body = client.post_json(
            "/v1/login", {"email": config.username, "password": config.password}
        )
    except ProviderClientError as exc:
        return False, describe_error(exc)
    finally:
        client.close()
    if not isinstance(body, dict) or not body.get("access_token"):
        return False, "Login succeeded but no access token was returned"
    return True, "Connection successful"


def _test_addic7ed(config: SubtitleProviderConfig) -> ConnectionTestResult:
    if (error := _require(config.username, "Username")) is not None:
        return False, error
    if (error := _require(config.password, "Password")) is not None:
        return False, error
    # No official API and no JSON responses — Addic7ed's login is an HTML form that can be
    # gated behind a reCAPTCHA (see Bazarr's addic7ed.py), which can't be solved here. This
    # mirrors Bazarr's own login flow instead (`addic7ed.py:151,181-196`): POST to
    # dologin.php, then read the same success/failure signals Bazarr does — a 302 on that
    # response means the login was accepted, specific response text means it wasn't.
    client = ProviderHttpClient("Addic7ed", "https://www.addic7ed.com")
    try:
        client.request("GET", "/login.php")
        login_response = client.request(
            "POST",
            "/dologin.php",
            data={
                "username": config.username,
                "password": config.password,
                "Submit": "Log in",
                "url": "",
                "remember": "true",
            },
        )
    except ProviderClientError as exc:
        return False, f"Addic7ed request failed: {exc}"
    finally:
        client.close()
    if "recaptcha" in login_response.text.lower():
        return False, (
            "Addic7ed is asking for a CAPTCHA — this can't be validated automatically, "
            "log in at addic7ed.com to confirm your credentials"
        )
    if "relax, slow down" in login_response.text:
        return False, "Addic7ed is rate-limiting login attempts — try again later"
    if "Wrong password" in login_response.text or "doesn't exist" in login_response.text:
        return False, "Wrong username or password"
    if login_response.status_code != 302:
        return False, "Addic7ed didn't accept the login — check your credentials"
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


def _test_anime_tosho(config: SubtitleProviderConfig) -> ConnectionTestResult:
    return _reachability_only("Anime Tosho", "https://feed.animetosho.org")


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
    "animetosho": _test_anime_tosho,
    "supersubtitles": _test_supersubtitles,
    "animekalesi": _test_animekalesi,
    "greeksubtitles": _test_greeksubtitles,
    "betaseries": _test_betaseries,
}
