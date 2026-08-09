import httpx
from legendarr_backend.http_client.client import ProviderClientError, ProviderHttpClient
from legendarr_backend.subtitle_acquisition.connection_tests import (
    test_connection as check_connection,
)
from legendarr_backend.subtitle_acquisition.models import (
    _API_KEY_KINDS,
    _USERNAME_PASSWORD_KINDS,
    SUBTITLE_PROVIDER_KINDS,
    SubtitleProviderConfig,
)


def _config(**overrides) -> SubtitleProviderConfig:
    data = {"kind": "opensubtitles", "enabled": True}
    data.update(overrides)
    return SubtitleProviderConfig(**data)


def test_unknown_kind_fails():
    success, message = check_connection(_config(kind="not-a-real-provider"))

    assert success is False
    assert "Unknown provider kind" in message


def test_opensubtitles_requires_api_key():
    success, message = check_connection(_config(kind="opensubtitles", api_key=None))

    assert success is False
    assert "API Key" in message


def test_opensubtitles_succeeds(monkeypatch):
    monkeypatch.setattr(ProviderHttpClient, "get_json", lambda self, path: {"level": "free"})

    success, message = check_connection(_config(kind="opensubtitles", api_key="a-key"))

    assert success is True


def test_opensubtitles_reports_rejected_key(monkeypatch):
    def _raise(self, path):
        request = httpx.Request("GET", "https://api.opensubtitles.com/api/v1/infos/user")
        response = httpx.Response(401, request=request)
        cause = httpx.HTTPStatusError("Unauthorized", request=request, response=response)
        raise ProviderClientError("failed with 401") from cause

    monkeypatch.setattr(ProviderHttpClient, "get_json", _raise)

    success, message = check_connection(_config(kind="opensubtitles", api_key="bad-key"))

    assert success is False
    assert "API Key" in message


def test_subdl_requires_api_key():
    success, message = check_connection(_config(kind="subdl", api_key=None))

    assert success is False


def test_subdl_succeeds(monkeypatch):
    monkeypatch.setattr(
        ProviderHttpClient, "get_json", lambda self, path: {"status": True, "subtitles": []}
    )

    success, message = check_connection(_config(kind="subdl", api_key="a-key"))

    assert success is True


def test_subdl_reports_rejected_key(monkeypatch):
    monkeypatch.setattr(
        ProviderHttpClient,
        "get_json",
        lambda self, path: {"status": False, "error": "Invalid API Key"},
    )

    success, message = check_connection(_config(kind="subdl", api_key="bad-key"))

    assert success is False
    assert message == "Invalid API Key"


def test_subsource_is_reachability_only(monkeypatch):
    monkeypatch.setattr(ProviderHttpClient, "ping", lambda self, path="/": None)

    success, message = check_connection(_config(kind="subsource", api_key="a-key"))

    assert success is True
    assert "isn't validated" in message


def test_subsource_requires_api_key():
    success, message = check_connection(_config(kind="subsource", api_key=None))

    assert success is False
    assert "API Key" in message


def test_legendas_net_requires_credentials():
    success, message = check_connection(_config(kind="legendas_net", username=None))

    assert success is False
    assert "Email" in message


def test_legendas_net_succeeds(monkeypatch):
    monkeypatch.setattr(
        ProviderHttpClient, "post_json", lambda self, path, json: {"access_token": "abc"}
    )

    success, message = check_connection(
        _config(kind="legendas_net", username="a@example.com", password="pw")
    )

    assert success is True


def test_legendas_net_fails_without_access_token(monkeypatch):
    monkeypatch.setattr(ProviderHttpClient, "post_json", lambda self, path, json: {"error": "no"})

    success, message = check_connection(
        _config(kind="legendas_net", username="a@example.com", password="pw")
    )

    assert success is False


def test_yify_subtitles_is_reachability_only(monkeypatch):
    monkeypatch.setattr(ProviderHttpClient, "ping", lambda self, path="/": None)

    success, message = check_connection(_config(kind="yify_subtitles"))

    assert success is True
    assert "no credential" in message


def test_yify_subtitles_reports_unreachable(monkeypatch):
    def _raise(self, path="/"):
        request = httpx.Request("GET", "https://yifysubtitles.ch/")
        raise ProviderClientError("YIFY Subtitles request failed") from httpx.ConnectError(
            "refused", request=request
        )

    monkeypatch.setattr(ProviderHttpClient, "ping", _raise)

    success, message = check_connection(_config(kind="yify_subtitles"))

    assert success is False


def test_tvsubtitles_reports_unreachable(monkeypatch):
    def _raise(self, path="/"):
        request = httpx.Request("GET", "http://www.tvsubtitles.net/")
        raise ProviderClientError("TVsubtitles request failed") from httpx.ConnectError(
            "refused", request=request
        )

    monkeypatch.setattr(ProviderHttpClient, "ping", _raise)

    success, message = check_connection(_config(kind="tvsubtitles"))

    assert success is False


def test_tvsubtitles_is_reachability_only(monkeypatch):
    monkeypatch.setattr(ProviderHttpClient, "ping", lambda self, path="/": None)

    success, message = check_connection(_config(kind="tvsubtitles"))

    assert success is True
    assert "no credential" in message


def test_napiprojekt_is_reachability_only(monkeypatch):
    monkeypatch.setattr(ProviderHttpClient, "ping", lambda self, path="/": None)

    success, message = check_connection(_config(kind="napiprojekt"))

    assert success is True


def test_napiprojekt_reports_unreachable(monkeypatch):
    def _raise(self, path="/"):
        request = httpx.Request("GET", "https://www.napiprojekt.pl/")
        raise ProviderClientError("Napiprojekt request failed") from httpx.ConnectError(
            "refused", request=request
        )

    monkeypatch.setattr(ProviderHttpClient, "ping", _raise)

    success, message = check_connection(_config(kind="napiprojekt"))

    assert success is False


def test_addic7ed_requires_credentials():
    success, message = check_connection(_config(kind="addic7ed", username=None))

    assert success is False
    assert "Username" in message


def test_addic7ed_succeeds(monkeypatch):
    def _request(self, method, path, data=None, follow_redirects=False):
        if method == "GET":
            return httpx.Response(200, request=httpx.Request("GET", "https://x/" + path))
        return httpx.Response(302, request=httpx.Request("POST", "https://x/" + path))

    monkeypatch.setattr(ProviderHttpClient, "request", _request)

    success, message = check_connection(_config(kind="addic7ed", username="u", password="p"))

    assert success is True


def test_addic7ed_reports_wrong_credentials(monkeypatch):
    def _request(self, method, path, data=None, follow_redirects=False):
        if method == "GET":
            return httpx.Response(200, request=httpx.Request("GET", "https://x/" + path))
        return httpx.Response(
            200, text="Wrong password", request=httpx.Request("POST", "https://x/" + path)
        )

    monkeypatch.setattr(ProviderHttpClient, "request", _request)

    success, message = check_connection(_config(kind="addic7ed", username="u", password="p"))

    assert success is False
    assert "Wrong" in message


def test_addic7ed_reports_captcha(monkeypatch):
    def _request(self, method, path, data=None, follow_redirects=False):
        if method == "GET":
            return httpx.Response(200, request=httpx.Request("GET", "https://x/" + path))
        return httpx.Response(
            200,
            text="<div class='g-recaptcha'></div>",
            request=httpx.Request("POST", "https://x/" + path),
        )

    monkeypatch.setattr(ProviderHttpClient, "request", _request)

    success, message = check_connection(_config(kind="addic7ed", username="u", password="p"))

    assert success is False
    assert "CAPTCHA" in message


def test_anime_tosho_is_reachability_only(monkeypatch):
    monkeypatch.setattr(ProviderHttpClient, "ping", lambda self, path="/": None)

    success, message = check_connection(_config(kind="animetosho"))

    assert success is True
    assert "no credential" in message


def test_anime_tosho_reports_unreachable(monkeypatch):
    def _raise(self, path="/"):
        request = httpx.Request("GET", "https://feed.animetosho.org/")
        raise ProviderClientError("Anime Tosho request failed") from httpx.ConnectError(
            "refused", request=request
        )

    monkeypatch.setattr(ProviderHttpClient, "ping", _raise)

    success, message = check_connection(_config(kind="animetosho"))

    assert success is False


def test_supersubtitles_is_reachability_only(monkeypatch):
    monkeypatch.setattr(ProviderHttpClient, "ping", lambda self, path="/": None)

    success, message = check_connection(_config(kind="supersubtitles"))

    assert success is True
    assert "no credential" in message


def test_supersubtitles_reports_unreachable(monkeypatch):
    def _raise(self, path="/"):
        request = httpx.Request("GET", "https://www.feliratok.eu/")
        raise ProviderClientError("Supersubtitles request failed") from httpx.ConnectError(
            "refused", request=request
        )

    monkeypatch.setattr(ProviderHttpClient, "ping", _raise)

    success, message = check_connection(_config(kind="supersubtitles"))

    assert success is False


def test_animekalesi_is_reachability_only(monkeypatch):
    monkeypatch.setattr(ProviderHttpClient, "ping", lambda self, path="/": None)

    success, message = check_connection(_config(kind="animekalesi"))

    assert success is True
    assert "no credential" in message


def test_animekalesi_reports_unreachable(monkeypatch):
    def _raise(self, path="/"):
        request = httpx.Request("GET", "https://www.animekalesi.com/")
        raise ProviderClientError("AnimeKalesi request failed") from httpx.ConnectError(
            "refused", request=request
        )

    monkeypatch.setattr(ProviderHttpClient, "ping", _raise)

    success, message = check_connection(_config(kind="animekalesi"))

    assert success is False


def test_greeksubtitles_is_reachability_only(monkeypatch):
    monkeypatch.setattr(ProviderHttpClient, "ping", lambda self, path="/": None)

    success, message = check_connection(_config(kind="greeksubtitles"))

    assert success is True
    assert "no credential" in message


def test_greeksubtitles_reports_unreachable(monkeypatch):
    def _raise(self, path="/"):
        request = httpx.Request("GET", "http://gr.greek-subtitles.com/")
        raise ProviderClientError("GreekSubtitles request failed") from httpx.ConnectError(
            "refused", request=request
        )

    monkeypatch.setattr(ProviderHttpClient, "ping", _raise)

    success, message = check_connection(_config(kind="greeksubtitles"))

    assert success is False


def test_betaseries_requires_api_key():
    success, message = check_connection(_config(kind="betaseries", api_key=None))

    assert success is False
    assert "API Token" in message


def test_betaseries_succeeds(monkeypatch):
    def _request(self, method, path, data=None, follow_redirects=False):
        return httpx.Response(
            400,
            json={"errors": [{"code": 4001}]},
            request=httpx.Request("GET", "https://api.betaseries.com/" + path),
        )

    monkeypatch.setattr(ProviderHttpClient, "request", _request)

    success, message = check_connection(_config(kind="betaseries", api_key="a-token"))

    assert success is True


def test_betaseries_reports_rejected_token(monkeypatch):
    def _request(self, method, path, data=None, follow_redirects=False):
        return httpx.Response(
            400,
            json={"errors": [{"code": 1001}]},
            request=httpx.Request("GET", "https://api.betaseries.com/" + path),
        )

    monkeypatch.setattr(ProviderHttpClient, "request", _request)

    success, message = check_connection(_config(kind="betaseries", api_key="bad-token"))

    assert success is False
    assert "API Token" in message


def test_credential_kinds_match_what_connection_tests_actually_requires(monkeypatch):
    """`models._API_KEY_KINDS`/`_USERNAME_PASSWORD_KINDS` (used for `has_credentials`/
    `is_configured` gating) and each `_test_*` function's own `_require()` calls encode the
    same fact in two places — this pins them together so a kind added to one but not the
    other fails loudly here instead of silently breaking gating."""
    for kind in _API_KEY_KINDS:
        success, message = check_connection(_config(kind=kind, api_key=None))
        assert success is False, f"{kind}: expected a missing-API-Key failure"
        assert "Unknown provider kind" not in message, f"{kind}: missing a _TESTERS entry"

    for kind in _USERNAME_PASSWORD_KINDS:
        success, message = check_connection(_config(kind=kind, username=None, password=None))
        assert success is False, f"{kind}: expected a missing-credential failure"
        assert "Unknown provider kind" not in message, f"{kind}: missing a _TESTERS entry"

    no_credential_kinds = set(SUBTITLE_PROVIDER_KINDS) - _API_KEY_KINDS - _USERNAME_PASSWORD_KINDS
    monkeypatch.setattr(ProviderHttpClient, "ping", lambda self, path="/": None)
    for kind in no_credential_kinds:
        success, message = check_connection(_config(kind=kind))
        assert success is True, f"{kind}: expected no credential requirement"
