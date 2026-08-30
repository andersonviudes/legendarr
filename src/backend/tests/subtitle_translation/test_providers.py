import pytest
from legendarr_backend.http_client.client import ProviderHttpClient
from legendarr_backend.subtitle_translation.models import TranslationProviderConfig
from legendarr_backend.subtitle_translation.providers.deepl import DeepLTranslationProvider
from legendarr_backend.subtitle_translation.providers.google import GoogleTranslationProvider
from legendarr_backend.subtitle_translation.providers.libretranslate import (
    LibreTranslateTranslationProvider,
)
from legendarr_backend.subtitle_translation.providers.llm import (
    DEFAULT_LLM_ENDPOINT,
    DEFAULT_LLM_MODEL,
    LLMTranslationProvider,
)


def _config(**overrides) -> TranslationProviderConfig:
    data = {"kind": "deepl", "enabled": True}
    data.update(overrides)
    return TranslationProviderConfig(**data)


def test_deepl_translate_batch_returns_translated_texts(monkeypatch):
    seen = {}

    def _post_json(self, path, json):
        seen["path"] = path
        seen["json"] = json
        return {"translations": [{"text": "olá"}, {"text": "mundo"}]}

    monkeypatch.setattr(ProviderHttpClient, "post_json", _post_json)
    monkeypatch.setattr(ProviderHttpClient, "close", lambda self: None)

    provider = DeepLTranslationProvider(_config(kind="deepl", api_key="a-key"))
    result = provider.translate_batch(["hello", "world"], "en", "pt")

    assert result == ["olá", "mundo"]
    assert seen["path"] == "/v2/translate"
    assert seen["json"] == {
        "text": ["hello", "world"],
        "source_lang": "EN",
        "target_lang": "PT",
    }


def test_deepl_translate_batch_uses_free_host_for_fx_suffixed_keys(monkeypatch):
    seen_hosts = []

    def _record_init(self, provider, base_url, headers=None, timeout=None):
        seen_hosts.append(base_url)

    monkeypatch.setattr(ProviderHttpClient, "__init__", _record_init)
    monkeypatch.setattr(
        ProviderHttpClient, "post_json", lambda self, path, json: {"translations": [{"text": ""}]}
    )
    monkeypatch.setattr(ProviderHttpClient, "close", lambda self: None)

    DeepLTranslationProvider(_config(kind="deepl", api_key="a-key:fx")).translate_batch(
        ["hi"], "en", "pt"
    )

    assert seen_hosts == ["https://api-free.deepl.com"]


def test_google_translate_batch_returns_translated_texts(monkeypatch):
    seen = {}

    def _post_json(self, path, json):
        seen["path"] = path
        seen["json"] = json
        return {"data": {"translations": [{"translatedText": "olá"}, {"translatedText": "mundo"}]}}

    monkeypatch.setattr(ProviderHttpClient, "post_json", _post_json)
    monkeypatch.setattr(ProviderHttpClient, "close", lambda self: None)

    provider = GoogleTranslationProvider(_config(kind="google", api_key="a-key"))
    result = provider.translate_batch(["hello", "world"], "en", "pt")

    assert result == ["olá", "mundo"]
    assert seen["path"] == "/language/translate/v2?key=a-key"
    assert seen["json"] == {
        "q": ["hello", "world"],
        "source": "en",
        "target": "pt",
        "format": "text",
    }


def test_google_translate_batch_chunks_requests_over_the_segment_limit(monkeypatch):
    seen_chunks = []

    def _post_json(self, path, json):
        seen_chunks.append(json["q"])
        return {"data": {"translations": [{"translatedText": f"t{text}"} for text in json["q"]]}}

    monkeypatch.setattr(ProviderHttpClient, "post_json", _post_json)
    monkeypatch.setattr(ProviderHttpClient, "close", lambda self: None)

    texts = [str(i) for i in range(150)]
    provider = GoogleTranslationProvider(_config(kind="google", api_key="a-key"))
    result = provider.translate_batch(texts, "en", "pt")

    assert result == [f"t{text}" for text in texts]
    assert [len(chunk) for chunk in seen_chunks] == [128, 22]


def test_libretranslate_translate_batch_returns_translated_texts(monkeypatch):
    seen = {}

    def _post_json(self, path, json):
        seen["path"] = path
        seen["json"] = json
        return {"translatedText": ["olá", "mundo"]}

    monkeypatch.setattr(ProviderHttpClient, "post_json", _post_json)
    monkeypatch.setattr(ProviderHttpClient, "close", lambda self: None)

    provider = LibreTranslateTranslationProvider(
        _config(kind="libretranslate", endpoint="http://localhost:5000")
    )
    result = provider.translate_batch(["hello", "world"], "en", "pt")

    assert result == ["olá", "mundo"]
    assert seen["path"] == "/translate"
    assert seen["json"] == {
        "q": ["hello", "world"],
        "source": "en",
        "target": "pt",
        "format": "text",
    }


def test_libretranslate_translate_batch_includes_api_key_when_configured(monkeypatch):
    seen = {}

    def _post_json(self, path, json):
        seen["json"] = json
        return {"translatedText": ["olá"]}

    monkeypatch.setattr(ProviderHttpClient, "post_json", _post_json)
    monkeypatch.setattr(ProviderHttpClient, "close", lambda self: None)

    provider = LibreTranslateTranslationProvider(
        _config(kind="libretranslate", endpoint="http://localhost:5000", api_key="secret")
    )
    provider.translate_batch(["hello"], "en", "pt")

    assert seen["json"]["api_key"] == "secret"


def test_llm_translate_batch_returns_translated_texts(monkeypatch):
    seen = {}

    def _post_json(self, path, json):
        seen["path"] = path
        seen["json"] = json
        return {"choices": [{"message": {"content": '{"translations": ["olá", "mundo"]}'}}]}

    monkeypatch.setattr(ProviderHttpClient, "post_json", _post_json)
    monkeypatch.setattr(ProviderHttpClient, "close", lambda self: None)

    provider = LLMTranslationProvider(
        _config(kind="llm", api_key="a-key", endpoint="http://localhost:11434/v1", model="llama3")
    )
    result = provider.translate_batch(["hello", "world"], "en", "pt")

    assert result == ["olá", "mundo"]
    assert seen["path"] == "/chat/completions"
    assert seen["json"]["model"] == "llama3"
    assert seen["json"]["messages"][1]["content"] == '["hello", "world"]'


def test_llm_translate_batch_defaults_endpoint_and_model_when_blank(monkeypatch):
    seen_hosts = []
    seen_models = []

    def _record_init(self, provider, base_url, headers=None, timeout=None):
        seen_hosts.append(base_url)

    def _post_json(self, path, json):
        seen_models.append(json["model"])
        return {"choices": [{"message": {"content": '{"translations": ["hi"]}'}}]}

    monkeypatch.setattr(ProviderHttpClient, "__init__", _record_init)
    monkeypatch.setattr(ProviderHttpClient, "post_json", _post_json)
    monkeypatch.setattr(ProviderHttpClient, "close", lambda self: None)

    LLMTranslationProvider(_config(kind="llm", api_key="a-key")).translate_batch(
        ["hello"], "en", "pt"
    )

    assert seen_hosts == [DEFAULT_LLM_ENDPOINT]
    assert seen_models == [DEFAULT_LLM_MODEL]


def test_llm_translate_batch_uses_default_prompt_when_blank(monkeypatch):
    seen_prompts = []

    def _post_json(self, path, json):
        seen_prompts.append(json["messages"][0]["content"])
        return {"choices": [{"message": {"content": '{"translations": ["oi"]}'}}]}

    monkeypatch.setattr(ProviderHttpClient, "post_json", _post_json)
    monkeypatch.setattr(ProviderHttpClient, "close", lambda self: None)

    provider = LLMTranslationProvider(_config(kind="llm", api_key="a-key"))
    provider.translate_batch(["hi"], "en", "pt")

    assert "en" in seen_prompts[0]
    assert "pt" in seen_prompts[0]
    assert "JSON" in seen_prompts[0]


def test_llm_translate_batch_uses_custom_prompt_template_when_set(monkeypatch):
    seen_prompts = []

    def _post_json(self, path, json):
        seen_prompts.append(json["messages"][0]["content"])
        return {"choices": [{"message": {"content": '{"translations": ["oi", "lá"]}'}}]}

    monkeypatch.setattr(ProviderHttpClient, "post_json", _post_json)
    monkeypatch.setattr(ProviderHttpClient, "close", lambda self: None)

    provider = LLMTranslationProvider(
        _config(
            kind="llm",
            api_key="a-key",
            prompt_template="Custom: {source} -> {target} ({count} lines)",
        )
    )
    provider.translate_batch(["hi", "there"], "en", "pt")

    assert seen_prompts[0] == "Custom: en -> pt (2 lines)"


def test_llm_translate_batch_raises_on_line_count_mismatch(monkeypatch):
    monkeypatch.setattr(
        ProviderHttpClient,
        "post_json",
        lambda self, path, json: {
            "choices": [{"message": {"content": '{"translations": ["only-one"]}'}}]
        },
    )
    monkeypatch.setattr(ProviderHttpClient, "close", lambda self: None)

    provider = LLMTranslationProvider(_config(kind="llm", api_key="a-key"))

    with pytest.raises(ValueError):
        provider.translate_batch(["hello", "world"], "en", "pt")
