"""Display metadata (label, which credential fields to render) for every translation
provider kind — the four built-ins plus whatever a dynamically-loaded plugin
(ROADMAP.md 0.9.0) declares. Single source of truth for both API responses
(`TranslationProviderConfigRead`) and the web provider-config form, which no longer
keeps its own copy of this table (see `legendarr_web.subtitle_translation.provider_display`).
"""

from legendarr_backend.subtitle_translation.plugins import (
    plugin_credential_fields,
    plugin_label,
)

BUILTIN_PROVIDER_LABELS: dict[str, str] = {
    "deepl": "DeepL",
    "google": "Google Translate",
    "libretranslate": "LibreTranslate",
    "llm": "LLM (OpenAI-compatible)",
}

# Which field(s) each kind's edit form shows — a superset of what `has_credentials`
# requires (e.g. `llm`'s `endpoint`/`model` are shown but optional, see `models.py`).
BUILTIN_PROVIDER_CREDENTIAL_FIELDS: dict[str, tuple[str, ...]] = {
    "deepl": ("api_key",),
    "google": ("api_key",),
    "libretranslate": ("endpoint", "api_key"),
    "llm": ("endpoint", "api_key", "model", "prompt_template"),
}


def provider_label(kind: str) -> str:
    if kind in BUILTIN_PROVIDER_LABELS:
        return BUILTIN_PROVIDER_LABELS[kind]
    return plugin_label(kind) or kind


def provider_credential_fields(kind: str) -> tuple[str, ...]:
    if kind in BUILTIN_PROVIDER_CREDENTIAL_FIELDS:
        return BUILTIN_PROVIDER_CREDENTIAL_FIELDS[kind]
    return plugin_credential_fields(kind)
