# Subtitle Translation

Translation backends implement a single `TranslationProvider` protocol:

```python
class TranslationProvider(Protocol):
    name: str

    def translate_batch(
        self, texts: list[str], source_language: str, target_language: str
    ) -> list[str]: ...
```

Every subtitle is translated in one call — every line goes out together and comes back in
the same order — instead of one request per line. This keeps the translation step decoupled
from whichever service does the actual work.

## Built-in providers

| Provider | Description |
| --- | --- |
| `echo` | Returns the input unchanged. Used for local development and tests. |
| `deepl` | [DeepL](https://www.deepl.com/) — needs an API Key. Free-tier (`:fx`-suffixed) keys are routed to the free-tier host automatically. |
| `google` | Google Cloud Translation (v2) — needs an API Key. |
| `libretranslate` | [LibreTranslate](https://libretranslate.com/) — self-hosted, needs an Endpoint URL; an API Key is only required by instances that opt into one. |
| `llm` | Any OpenAI-compatible `/chat/completions` API — OpenAI itself, or a self-hosted/third-party endpoint that speaks the same protocol (Ollama, LM Studio, OpenRouter, Groq, ...). Needs an API Key; Endpoint and Model both default (to `https://api.openai.com/v1` and `gpt-4o-mini`) when left blank. |

`deepl`, `google`, `libretranslate`, and `llm` are registered and credentialed from
`/settings/translation-providers/`: enable the ones you want, fill in whichever credential
fields they need, and use "Test connection" to confirm they're reachable before relying on
them. `echo` needs no credentials and is always available, for development.

## Provider selection

Provider selection is a **global** setting, not a per-[language profile](language-profiles.md)
field — a `LanguageProfile` only says which languages to translate into, not which engine to
use. From `/settings/translation-providers/`, one enabled and credentialed provider can be
marked the default. A translation job tries the default first, then falls through every other
enabled, credentialed provider in `id` order if the default fails or isn't set — so a job never
fails outright just because one engine is briefly unavailable, as long as another is configured.
