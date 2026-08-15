import httpx
from legendarr_backend.http_client.client import ProviderClientError, ProviderHttpClient
from legendarr_backend.subtitle_translation.connection_tests import (
    test_connection as check_connection,
)
from legendarr_backend.subtitle_translation.models import (
    _API_KEY_KINDS,
    _ENDPOINT_KINDS,
    TRANSLATION_PROVIDER_KINDS,
    TranslationProviderConfig,
)


def _config(**overrides) -> TranslationProviderConfig:
    data = {"kind": "deepl", "enabled": True}
    data.update(overrides)
    return TranslationProviderConfig(**data)


def test_unknown_kind_fails():
    success, message = check_connection(_config(kind="not-a-real-provider"))

    assert success is False
    assert "Unknown provider kind" in message


def test_deepl_requires_api_key():
    success, message = check_connection(_config(kind="deepl", api_key=None))

    assert success is False
    assert "API Key" in message


def test_deepl_succeeds(monkeypatch):
    monkeypatch.setattr(ProviderHttpClient, "get_json", lambda self, path: {"character_count": 0})

    success, message = check_connection(_config(kind="deepl", api_key="a-key"))

    assert success is True


def test_deepl_reports_rejected_key(monkeypatch):
    def _raise(self, path):
        request = httpx.Request("GET", "https://api.deepl.com/v2/usage")
        response = httpx.Response(403, request=request)
        cause = httpx.HTTPStatusError("Forbidden", request=request, response=response)
        raise ProviderClientError("failed with 403") from cause

    monkeypatch.setattr(ProviderHttpClient, "get_json", _raise)

    success, message = check_connection(_config(kind="deepl", api_key="bad-key"))

    assert success is False
    assert "API Key" in message


def test_deepl_uses_the_free_host_for_fx_suffixed_keys(monkeypatch):
    seen_hosts = []

    def _record_init(self, provider, base_url, headers=None, timeout=None):
        seen_hosts.append(base_url)

    monkeypatch.setattr(ProviderHttpClient, "__init__", _record_init)
    monkeypatch.setattr(ProviderHttpClient, "get_json", lambda self, path: {})
    monkeypatch.setattr(ProviderHttpClient, "close", lambda self: None)

    check_connection(_config(kind="deepl", api_key="a-key:fx"))
    check_connection(_config(kind="deepl", api_key="a-key"))

    assert seen_hosts == ["https://api-free.deepl.com", "https://api.deepl.com"]


def test_google_requires_api_key():
    success, message = check_connection(_config(kind="google", api_key=None))

    assert success is False
    assert "API Key" in message


def test_google_succeeds(monkeypatch):
    monkeypatch.setattr(ProviderHttpClient, "get_json", lambda self, path: {"data": {}})

    success, message = check_connection(_config(kind="google", api_key="a-key"))

    assert success is True


def test_google_reports_rejected_key(monkeypatch):
    def _raise(self, path):
        request = httpx.Request("GET", "https://translation.googleapis.com/language")
        response = httpx.Response(400, request=request)
        cause = httpx.HTTPStatusError("Bad Request", request=request, response=response)
        raise ProviderClientError("failed with 400") from cause

    monkeypatch.setattr(ProviderHttpClient, "get_json", _raise)

    success, message = check_connection(_config(kind="google", api_key="bad-key"))

    assert success is False


def test_google_redacts_api_key_from_error_message(monkeypatch):
    """The key travels in the query string (Google's v2 API has no header option), so a
    raw `str(exc)` fallback — which embeds the request URL — must not leak it back out."""

    def _raise(self, path):
        request = httpx.Request(
            "GET",
            "https://translation.googleapis.com/language/translate/v2/languages?key=super-secret",
        )
        cause = httpx.ConnectError("connection refused", request=request)
        raise ProviderClientError(f"Google Translate request failed: {cause}") from cause

    monkeypatch.setattr(ProviderHttpClient, "get_json", _raise)

    success, message = check_connection(_config(kind="google", api_key="super-secret"))

    assert success is False
    assert "super-secret" not in message


def test_libretranslate_requires_endpoint():
    success, message = check_connection(_config(kind="libretranslate", endpoint=None))

    assert success is False
    assert "Endpoint" in message


def test_libretranslate_succeeds(monkeypatch):
    monkeypatch.setattr(ProviderHttpClient, "get_json", lambda self, path: [])

    success, message = check_connection(
        _config(kind="libretranslate", endpoint="http://localhost:5000")
    )

    assert success is True


def test_libretranslate_reports_unreachable(monkeypatch):
    def _raise(self, path):
        raise ProviderClientError("LibreTranslate request failed: connection refused")

    monkeypatch.setattr(ProviderHttpClient, "get_json", _raise)

    success, message = check_connection(
        _config(kind="libretranslate", endpoint="http://localhost:5000")
    )

    assert success is False


def test_llm_requires_api_key():
    success, message = check_connection(_config(kind="llm", api_key=None))

    assert success is False
    assert "API Key" in message


def test_llm_succeeds(monkeypatch):
    monkeypatch.setattr(ProviderHttpClient, "get_json", lambda self, path: {"data": []})

    success, message = check_connection(_config(kind="llm", api_key="a-key"))

    assert success is True


def test_llm_reports_unreachable(monkeypatch):
    def _raise(self, path):
        raise ProviderClientError("LLM request failed: connection refused")

    monkeypatch.setattr(ProviderHttpClient, "get_json", _raise)

    success, message = check_connection(_config(kind="llm", api_key="a-key"))

    assert success is False


def test_credential_kinds_match_what_connection_tests_actually_requires():
    """`models._API_KEY_KINDS`/`_ENDPOINT_KINDS` (used for `has_credentials`/`is_configured`
    gating) and each `_test_*` function's own `_require()` calls encode the same fact in two
    places — this pins them together so a kind added to one but not the other fails loudly
    here instead of silently breaking gating."""
    for kind in _API_KEY_KINDS:
        success, message = check_connection(_config(kind=kind, api_key=None))
        assert success is False, f"{kind}: expected a missing-API-Key failure"
        assert "Unknown provider kind" not in message, f"{kind}: missing a _TESTERS entry"

    for kind in _ENDPOINT_KINDS:
        success, message = check_connection(_config(kind=kind, endpoint=None))
        assert success is False, f"{kind}: expected a missing-endpoint failure"
        assert "Unknown provider kind" not in message, f"{kind}: missing a _TESTERS entry"

    assert set(TRANSLATION_PROVIDER_KINDS) == _API_KEY_KINDS | _ENDPOINT_KINDS
