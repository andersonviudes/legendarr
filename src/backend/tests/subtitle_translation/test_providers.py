from legendarr_backend.http_client.client import ProviderHttpClient
from legendarr_backend.subtitle_translation.models import TranslationProviderConfig
from legendarr_backend.subtitle_translation.providers.deepl import DeepLTranslationProvider
from legendarr_backend.subtitle_translation.providers.google import GoogleTranslationProvider
from legendarr_backend.subtitle_translation.providers.libretranslate import (
    LibreTranslateTranslationProvider,
)


def _config(**overrides) -> TranslationProviderConfig:
    data = {"kind": "deepl", "enabled": True}
    data.update(overrides)
    return TranslationProviderConfig(**data)


def test_deepl_translate_returns_translated_text(monkeypatch):
    seen = {}

    def _post_json(self, path, json):
        seen["path"] = path
        seen["json"] = json
        return {"translations": [{"text": "olá"}]}

    monkeypatch.setattr(ProviderHttpClient, "post_json", _post_json)
    monkeypatch.setattr(ProviderHttpClient, "close", lambda self: None)

    provider = DeepLTranslationProvider(_config(kind="deepl", api_key="a-key"))
    result = provider.translate("hello", "en", "pt")

    assert result == "olá"
    assert seen["path"] == "/v2/translate"
    assert seen["json"] == {"text": ["hello"], "source_lang": "EN", "target_lang": "PT"}


def test_deepl_translate_uses_free_host_for_fx_suffixed_keys(monkeypatch):
    seen_hosts = []

    def _record_init(self, provider, base_url, headers=None, timeout=None):
        seen_hosts.append(base_url)

    monkeypatch.setattr(ProviderHttpClient, "__init__", _record_init)
    monkeypatch.setattr(
        ProviderHttpClient, "post_json", lambda self, path, json: {"translations": [{"text": ""}]}
    )
    monkeypatch.setattr(ProviderHttpClient, "close", lambda self: None)

    DeepLTranslationProvider(_config(kind="deepl", api_key="a-key:fx")).translate("hi", "en", "pt")

    assert seen_hosts == ["https://api-free.deepl.com"]


def test_google_translate_returns_translated_text(monkeypatch):
    seen = {}

    def _post_json(self, path, json):
        seen["path"] = path
        seen["json"] = json
        return {"data": {"translations": [{"translatedText": "olá"}]}}

    monkeypatch.setattr(ProviderHttpClient, "post_json", _post_json)
    monkeypatch.setattr(ProviderHttpClient, "close", lambda self: None)

    provider = GoogleTranslationProvider(_config(kind="google", api_key="a-key"))
    result = provider.translate("hello", "en", "pt")

    assert result == "olá"
    assert seen["path"] == "/language/translate/v2?key=a-key"
    assert seen["json"] == {"q": "hello", "source": "en", "target": "pt", "format": "text"}


def test_libretranslate_translate_returns_translated_text(monkeypatch):
    seen = {}

    def _post_json(self, path, json):
        seen["path"] = path
        seen["json"] = json
        return {"translatedText": "olá"}

    monkeypatch.setattr(ProviderHttpClient, "post_json", _post_json)
    monkeypatch.setattr(ProviderHttpClient, "close", lambda self: None)

    provider = LibreTranslateTranslationProvider(
        _config(kind="libretranslate", endpoint="http://localhost:5000")
    )
    result = provider.translate("hello", "en", "pt")

    assert result == "olá"
    assert seen["path"] == "/translate"
    assert seen["json"] == {"q": "hello", "source": "en", "target": "pt", "format": "text"}


def test_libretranslate_translate_includes_api_key_when_configured(monkeypatch):
    seen = {}

    def _post_json(self, path, json):
        seen["json"] = json
        return {"translatedText": "olá"}

    monkeypatch.setattr(ProviderHttpClient, "post_json", _post_json)
    monkeypatch.setattr(ProviderHttpClient, "close", lambda self: None)

    provider = LibreTranslateTranslationProvider(
        _config(kind="libretranslate", endpoint="http://localhost:5000", api_key="secret")
    )
    provider.translate("hello", "en", "pt")

    assert seen["json"]["api_key"] == "secret"
