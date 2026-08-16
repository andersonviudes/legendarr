from typing import Protocol


class TranslationProvider(Protocol):
    """Contract every translation backend (DeepL, Google, LibreTranslate, ...) must satisfy."""

    name: str

    def translate_batch(
        self, texts: list[str], source_language: str, target_language: str
    ) -> list[str]: ...


class PluginTranslationProvider(TranslationProvider, Protocol):
    """Extra shape a dynamically-loaded `TranslationProvider` (ROADMAP.md 0.9.0) must
    satisfy on top of the base contract, so it can slot into the same catalog/UI
    machinery as the built-in providers — seeding, credential gating, and the web
    provider-config form. Checked by `subtitle_translation.plugins.load_plugin_providers`
    at import time; a class missing any of these is skipped, not crashed on.
    """

    kind: str
    label: str
    # Subset of ("api_key", "endpoint", "model", "prompt_template") — the provider
    # config columns this provider's edit form should render.
    credential_fields: tuple[str, ...]
    # Subset of `credential_fields` that must be set for `has_credentials` to be True.
    required_credential_fields: tuple[str, ...]
    # Checked against `plugins.SUPPORTED_PLUGIN_API_VERSION`; a mismatch is skipped.
    plugin_api_version: int

    # `test_connection` is optional — a plugin may define it as a `staticmethod`/
    # `classmethod` with this signature to back the "Test connection" button; a plugin
    # without one falls back to a generic "configuration saved" result
    # (`connection_tests.test_connection`). Not part of this Protocol since it isn't
    # required for a plugin to load.
