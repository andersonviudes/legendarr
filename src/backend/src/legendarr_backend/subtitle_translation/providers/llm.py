import json

from legendarr_backend.http_client.client import ProviderHttpClient
from legendarr_backend.http_client.rate_limit import retry_on_rate_limit
from legendarr_backend.subtitle_translation.models import TranslationProviderConfig

# Generic OpenAI-compatible defaults — a blank `endpoint`/`model` on the config falls back
# to these rather than requiring the user to type them, same as every other provider here
# needs no fallback because its one required field (`api_key`) has no sensible default.
DEFAULT_LLM_ENDPOINT = "https://api.openai.com/v1"
DEFAULT_LLM_MODEL = "gpt-4o-mini"

# How many subtitle lines go out per chat-completions request. A feature-length subtitle
# asked for in one call needs more output tokens than most models will emit, so the reply
# comes back truncated and then fails the count check in `_translate_chunk` — the whole
# translation lost to a limit that has nothing to do with the input. Bazarr's Gemini
# translator batches at the same 300.
LLM_BATCH_SIZE = 300

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

    Unlike DeepL/Google, batching isn't just "one request instead of N" — an LLM's system
    prompt lets a large run of subtitle lines go out as a single call, which matters for
    cost and rate limits far more than it does for the other providers. It still can't be
    the *whole* subtitle, hence `LLM_BATCH_SIZE`.
    """

    name = "llm"
    # What this provider is called in HTTP error messages, which surface in "Test
    # connection" and in `TranslationFailure.error_message` on the History page.
    client_label = "LLM"
    # Overridden by a subclass that pins this same protocol to one vendor (see
    # `providers/gemini.py`). A config's own `endpoint`/`model` still win over both.
    default_endpoint = DEFAULT_LLM_ENDPOINT
    default_model = DEFAULT_LLM_MODEL

    def __init__(self, config: TranslationProviderConfig) -> None:
        self._api_key = config.api_key
        self._endpoint = config.endpoint or self.default_endpoint
        self._model = config.model or self.default_model
        # ROADMAP.md 0.9.0 — user-editable system prompt. Blank falls back to
        # `_SYSTEM_PROMPT`, validated (via a dummy `.format()`) at save time in
        # `router.py`, not here.
        self._prompt_template = config.prompt_template or _SYSTEM_PROMPT

    def translate_batch(
        self, texts: list[str], source_language: str, target_language: str
    ) -> list[str]:
        client = ProviderHttpClient(
            self.client_label,
            self._endpoint,
            headers={"Authorization": f"Bearer {self._api_key}"},
        )
        try:
            translated: list[str] = []
            for start in range(0, len(texts), LLM_BATCH_SIZE):
                chunk = texts[start : start + LLM_BATCH_SIZE]
                translated.extend(
                    self._translate_chunk(client, chunk, source_language, target_language)
                )
        finally:
            client.close()
        return translated

    def _translate_chunk(
        self,
        client: ProviderHttpClient,
        texts: list[str],
        source_language: str,
        target_language: str,
    ) -> list[str]:
        response = retry_on_rate_limit(
            lambda: client.post_json(
                "/chat/completions",
                {
                    "model": self._model,
                    "messages": [
                        {
                            "role": "system",
                            "content": self._prompt_template.format(
                                source=source_language,
                                target=target_language,
                                count=len(texts),
                            ),
                        },
                        {"role": "user", "content": json.dumps(texts)},
                    ],
                    "response_format": {"type": "json_object"},
                },
            ),
            description=self.client_label,
        )
        translations = json.loads(response["choices"][0]["message"]["content"])["translations"]
        if len(translations) != len(texts):
            raise ValueError(
                f"{self.client_label} returned {len(translations)} translations "
                f"for {len(texts)} lines"
            )
        return translations
