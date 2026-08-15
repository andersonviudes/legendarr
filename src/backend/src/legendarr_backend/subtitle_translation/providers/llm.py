import json

from legendarr_backend.http_client.client import ProviderHttpClient
from legendarr_backend.subtitle_translation.models import TranslationProviderConfig

# Generic OpenAI-compatible defaults — a blank `endpoint`/`model` on the config falls back
# to these rather than requiring the user to type them, same as every other provider here
# needs no fallback because its one required field (`api_key`) has no sensible default.
DEFAULT_LLM_ENDPOINT = "https://api.openai.com/v1"
DEFAULT_LLM_MODEL = "gpt-4o-mini"

_SYSTEM_PROMPT = (
    "You translate subtitle lines from {source} to {target}. You will receive a JSON array "
    "of {count} strings. Reply with a JSON object of the exact shape "
    '{{"translations": [...]}} containing exactly {count} translated strings, in the same '
    "order, with no other text. Preserve line breaks within each string and don't merge or "
    "split lines."
)


class LLMTranslationProvider:
    """Real `translate_batch()` backend for any OpenAI-compatible chat-completions API
    (OpenAI itself, or a self-hosted/third-party endpoint that speaks the same protocol —
    Ollama, LM Studio, OpenRouter, Groq, ...), for a configured `TranslationProviderConfig`.

    Unlike DeepL/Google/LibreTranslate, batching isn't just "one request instead of N" —
    an LLM's system prompt lets the whole subtitle go out as a single call, which matters
    for cost and rate limits far more than it does for the other providers.
    """

    name = "llm"

    def __init__(self, config: TranslationProviderConfig) -> None:
        self._api_key = config.api_key
        self._endpoint = config.endpoint or DEFAULT_LLM_ENDPOINT
        self._model = config.model or DEFAULT_LLM_MODEL

    def translate_batch(
        self, texts: list[str], source_language: str, target_language: str
    ) -> list[str]:
        client = ProviderHttpClient(
            "LLM", self._endpoint, headers={"Authorization": f"Bearer {self._api_key}"}
        )
        try:
            response = client.post_json(
                "/chat/completions",
                {
                    "model": self._model,
                    "messages": [
                        {
                            "role": "system",
                            "content": _SYSTEM_PROMPT.format(
                                source=source_language, target=target_language, count=len(texts)
                            ),
                        },
                        {"role": "user", "content": json.dumps(texts)},
                    ],
                    "response_format": {"type": "json_object"},
                },
            )
        finally:
            client.close()
        translations = json.loads(response["choices"][0]["message"]["content"])["translations"]
        if len(translations) != len(texts):
            raise ValueError(
                f"LLM returned {len(translations)} translations for {len(texts)} lines"
            )
        return translations
