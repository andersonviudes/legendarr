PROVIDER_LABELS = {
    "deepl": "DeepL",
    "google": "Google Translate",
    "libretranslate": "LibreTranslate",
    "llm": "LLM (OpenAI-compatible)",
}

# Which credential fields the edit form shows for each provider kind — matches the auth
# shapes `legendarr_backend.subtitle_translation.connection_tests` checks against.
PROVIDER_CREDENTIAL_FIELDS = {
    "deepl": ("api_key",),
    "google": ("api_key",),
    "libretranslate": ("endpoint", "api_key"),
    "llm": ("endpoint", "api_key", "model"),
}


def provider_label(kind: str) -> str:
    return PROVIDER_LABELS.get(kind, kind)


def provider_credential_fields(kind: str) -> tuple[str, ...]:
    return PROVIDER_CREDENTIAL_FIELDS.get(kind, ())
