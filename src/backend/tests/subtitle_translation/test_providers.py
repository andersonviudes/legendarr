import json as json_lib
from urllib.parse import parse_qs, urlparse

import pytest
from legendarr_backend.http_client.client import ProviderClientError, ProviderHttpClient
from legendarr_backend.subtitle_translation.models import TranslationProviderConfig
from legendarr_backend.subtitle_translation.providers.deepl import DeepLTranslationProvider
from legendarr_backend.subtitle_translation.providers.gemini import (
    GEMINI_ENDPOINT,
    GEMINI_MODEL,
    GeminiTranslationProvider,
)
from legendarr_backend.subtitle_translation.providers.google import (
    GOOGLE_FREE_USER_AGENT,
    GoogleCloudTranslationProvider,
    GoogleFreeTranslationProvider,
    build_google_provider,
)
from legendarr_backend.subtitle_translation.providers.libretranslate import (
    LibreTranslateTranslationProvider,
)
from legendarr_backend.subtitle_translation.providers.llm import (
    DEFAULT_LLM_ENDPOINT,
    DEFAULT_LLM_MODEL,
    LLM_BATCH_SIZE,
    LLMTranslationProvider,
)


def _config(**overrides) -> TranslationProviderConfig:
    data = {"kind": "deepl", "enabled": True}
    data.update(overrides)
    return TranslationProviderConfig(**data)


def _requested_text(path: str) -> str:
    """The `q` parameter of a keyless `translate_a/single` request."""
    return parse_qs(urlparse(path).query)["q"][0]


def _echo_translation(path: str) -> list:
    """A `translate_a/single` response translating the requested text to `t-<text>`."""
    text = _requested_text(path)
    return [[[f"t-{text}", text, None, None, 10]], None, "en"]


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

    provider = GoogleCloudTranslationProvider(_config(kind="google", api_key="a-key"))
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
    provider = GoogleCloudTranslationProvider(_config(kind="google", api_key="a-key"))
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


def test_google_free_translate_batch_joins_the_sentence_segments(monkeypatch):
    seen_paths = []

    def _get_json(self, path):
        seen_paths.append(path)
        return [
            [["Olá. ", "Hello. ", None, None, 10], ["Mundo", "World", None, None, 10]],
            None,
            "en",
        ]

    monkeypatch.setattr(ProviderHttpClient, "get_json", _get_json)
    monkeypatch.setattr(ProviderHttpClient, "close", lambda self: None)

    provider = GoogleFreeTranslationProvider(_config(kind="google"))
    result = provider.translate_batch(["Hello. World"], "en", "pt-BR")

    assert result == ["Olá. Mundo"]
    assert seen_paths[0].startswith("/translate_a/single?")
    query = parse_qs(urlparse(seen_paths[0]).query)
    assert query["client"] == ["gtx"]
    assert query["sl"] == ["en"]
    # The regional subtag survives — normalizing "pt-BR" to "pt" would translate to the
    # wrong variant.
    assert query["tl"] == ["pt-BR"]


def test_google_free_translate_batch_keeps_line_order_across_the_fan_out(monkeypatch):
    monkeypatch.setattr(ProviderHttpClient, "get_json", lambda self, path: _echo_translation(path))
    monkeypatch.setattr(ProviderHttpClient, "close", lambda self: None)

    texts = [str(index) for index in range(50)]
    provider = GoogleFreeTranslationProvider(_config(kind="google"))

    assert provider.translate_batch(texts, "en", "pt") == [f"t-{text}" for text in texts]


def test_google_free_translate_batch_sends_a_browser_user_agent(monkeypatch):
    seen_headers = []

    def _record_init(self, provider, base_url, headers=None, timeout=None):
        seen_headers.append(headers)

    monkeypatch.setattr(ProviderHttpClient, "__init__", _record_init)
    monkeypatch.setattr(ProviderHttpClient, "get_json", lambda self, path: _echo_translation(path))
    monkeypatch.setattr(ProviderHttpClient, "close", lambda self: None)

    GoogleFreeTranslationProvider(_config(kind="google")).translate_batch(["hi"], "en", "pt")

    assert seen_headers == [{"User-Agent": GOOGLE_FREE_USER_AGENT}]


def test_google_free_translate_batch_does_not_request_blank_lines(monkeypatch):
    requested = []

    def _get_json(self, path):
        requested.append(_requested_text(path))
        return _echo_translation(path)

    monkeypatch.setattr(ProviderHttpClient, "get_json", _get_json)
    monkeypatch.setattr(ProviderHttpClient, "close", lambda self: None)

    provider = GoogleFreeTranslationProvider(_config(kind="google"))
    result = provider.translate_batch(["hello", "   ", ""], "en", "pt")

    assert result == ["t-hello", "   ", ""]
    assert requested == ["hello"]


def test_google_free_translate_batch_keeps_source_text_for_a_few_failed_lines(monkeypatch):
    def _get_json(self, path):
        if _requested_text(path) == "7":
            raise ProviderClientError("Google Translate said no")
        return _echo_translation(path)

    monkeypatch.setattr(ProviderHttpClient, "get_json", _get_json)
    monkeypatch.setattr(ProviderHttpClient, "close", lambda self: None)

    texts = [str(index) for index in range(50)]
    provider = GoogleFreeTranslationProvider(_config(kind="google"))
    result = provider.translate_batch(texts, "en", "pt")

    assert result[7] == "7"
    assert result[6] == "t-6"


def test_google_free_translate_batch_raises_when_too_many_lines_fail(monkeypatch):
    def _get_json(self, path):
        raise ProviderClientError("Google Translate said no")

    monkeypatch.setattr(ProviderHttpClient, "get_json", _get_json)
    monkeypatch.setattr(ProviderHttpClient, "close", lambda self: None)

    provider = GoogleFreeTranslationProvider(_config(kind="google"))

    with pytest.raises(ProviderClientError, match="10 of 10"):
        provider.translate_batch([str(index) for index in range(10)], "en", "pt")


def test_build_google_provider_picks_the_cloud_api_when_a_key_is_set():
    provider = build_google_provider(_config(kind="google", api_key="a-key"))

    assert isinstance(provider, GoogleCloudTranslationProvider)
    assert provider.name == "google"


def test_build_google_provider_picks_the_free_endpoint_without_a_key():
    provider = build_google_provider(_config(kind="google"))

    assert isinstance(provider, GoogleFreeTranslationProvider)
    # Both backends report the same name, so circuit-breaker state and recorded attempts
    # don't split in two when a user adds or removes their key.
    assert provider.name == "google"


def test_llm_translate_batch_chunks_requests_over_the_batch_size(monkeypatch):
    seen_chunks = []
    seen_counts = []

    def _post_json(self, path, payload):
        chunk = json_lib.loads(payload["messages"][1]["content"])
        seen_chunks.append(chunk)
        seen_counts.append(payload["messages"][0]["content"])
        translations = json_lib.dumps({"translations": [f"t{text}" for text in chunk]})
        return {"choices": [{"message": {"content": translations}}]}

    monkeypatch.setattr(ProviderHttpClient, "post_json", _post_json)
    monkeypatch.setattr(ProviderHttpClient, "close", lambda self: None)

    texts = [str(index) for index in range(LLM_BATCH_SIZE + 20)]
    provider = LLMTranslationProvider(_config(kind="llm", api_key="a-key"))
    result = provider.translate_batch(texts, "en", "pt")

    assert result == [f"t{text}" for text in texts]
    assert [len(chunk) for chunk in seen_chunks] == [LLM_BATCH_SIZE, 20]
    # The prompt's `{count}` describes the chunk it's sent with, not the whole subtitle.
    assert str(LLM_BATCH_SIZE) in seen_counts[0]
    assert "20" in seen_counts[1]


def test_gemini_translate_batch_defaults_to_ai_studio_and_flash(monkeypatch):
    seen_hosts = []
    seen_models = []

    def _record_init(self, provider, base_url, headers=None, timeout=None):
        seen_hosts.append(base_url)

    def _post_json(self, path, payload):
        seen_models.append(payload["model"])
        return {"choices": [{"message": {"content": '{"translations": ["olá"]}'}}]}

    monkeypatch.setattr(ProviderHttpClient, "__init__", _record_init)
    monkeypatch.setattr(ProviderHttpClient, "post_json", _post_json)
    monkeypatch.setattr(ProviderHttpClient, "close", lambda self: None)

    result = GeminiTranslationProvider(_config(kind="gemini", api_key="a-key")).translate_batch(
        ["hello"], "en", "pt"
    )

    assert result == ["olá"]
    assert seen_hosts == [GEMINI_ENDPOINT]
    assert seen_models == [GEMINI_MODEL]


def test_gemini_translate_batch_honors_a_configured_model(monkeypatch):
    seen_models = []

    def _post_json(self, path, payload):
        seen_models.append(payload["model"])
        return {"choices": [{"message": {"content": '{"translations": ["olá"]}'}}]}

    monkeypatch.setattr(ProviderHttpClient, "post_json", _post_json)
    monkeypatch.setattr(ProviderHttpClient, "close", lambda self: None)

    GeminiTranslationProvider(
        _config(kind="gemini", api_key="a-key", model="gemini-2.5-pro")
    ).translate_batch(["hello"], "en", "pt")

    assert seen_models == ["gemini-2.5-pro"]
