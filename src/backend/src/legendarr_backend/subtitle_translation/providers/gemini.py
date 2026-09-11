from legendarr_backend.subtitle_translation.providers.llm import LLMTranslationProvider

# Google AI Studio exposes Gemini behind an OpenAI-compatible surface — the same
# `/chat/completions` protocol `LLMTranslationProvider` already speaks, including
# `response_format: {"type": "json_object"}`. So the only thing this provider changes is
# where it points and what it defaults to.
GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/openai"
GEMINI_MODEL = "gemini-2.0-flash"


class GeminiTranslationProvider(LLMTranslationProvider):
    """Gemini via Google AI Studio — the highest-quality provider here that's usable on a
    free API key, and the reason it gets its own kind instead of being a documented `llm`
    preset: the user pastes an AI Studio key and nothing else, no endpoint or model name
    to look up.

    `endpoint` is deliberately absent from its `credential_fields`
    (`provider_catalog.py`), so `GEMINI_ENDPOINT` is effectively fixed; `model` stays
    editable so a newer Flash/Pro can be picked without a release.
    """

    name = "gemini"
    client_label = "Gemini"
    default_endpoint = GEMINI_ENDPOINT
    default_model = GEMINI_MODEL
