from datetime import datetime
from typing import Literal, get_args

from sqlalchemy import Column
from sqlmodel import Field, SQLModel

from legendarr_backend.security.encrypted_string import EncryptedString

# Single source of truth for every recognized translation provider kind.
TranslationProviderKind = Literal["deepl", "google", "libretranslate", "llm"]

# Derived from the Literal above rather than hand-duplicated, so the two can't drift apart.
TRANSLATION_PROVIDER_KINDS: tuple[TranslationProviderKind, ...] = get_args(TranslationProviderKind)

# Which credential(s) each kind needs to be usable — mirrors the `_require()` checks in
# `connection_tests.py`. Unlike subtitle sources, every translation provider kind needs at
# least one of these today, so there's no "no credential concept" branch (yet).
_API_KEY_KINDS = {"deepl", "google", "llm"}
_ENDPOINT_KINDS = {"libretranslate"}


class TranslationProviderConfig(SQLModel, table=True):
    """Registration/credentials for one of the fixed `TRANSLATION_PROVIDER_KINDS`.

    The catalog is fixed (one row per kind, seeded at startup) rather than user-created
    like `ArrService` — mirrors `SubtitleProviderConfig`'s shape. `echo` (the dev-only
    in-code provider) has no row here; it needs no credentials and isn't user-configurable.
    """

    id: int | None = Field(default=None, primary_key=True)
    kind: str = Field(index=True, unique=True)
    enabled: bool = Field(default=True)
    api_key: str | None = Field(default=None, sa_column=Column(EncryptedString))
    # Self-hosted engines (libretranslate) need their own base URL. Ignored for every other
    # kind, same way `SubtitleProviderConfig`'s OpenSubtitles-only search options are ignored
    # for every kind but opensubtitles.
    endpoint: str | None = Field(default=None)
    # The LLM's model name (e.g. "gpt-4o-mini"). Ignored for every other kind, same shape as
    # `endpoint` above — optional, `LLMTranslationProvider` falls back to a sensible default
    # when blank rather than requiring the user to type one.
    model: str | None = Field(default=None)
    # Custom system-prompt template for an LLM-backed provider (built-in `llm`, or a
    # plugin that opts into it — ROADMAP.md 0.9.0). Blank falls back to the provider's
    # own hardcoded default. Ignored for any kind that doesn't declare
    # `"prompt_template"` in its `credential_fields`.
    prompt_template: str | None = Field(default=None)
    connection_verified: bool = Field(default=False)

    @property
    def has_credentials(self) -> bool:
        """Whether this provider has the credential(s) its kind needs — the web UI uses
        this to gate the enable toggle so a provider can't be switched on before it's
        actually usable."""
        if self.kind in _API_KEY_KINDS:
            return bool(self.api_key)
        if self.kind in _ENDPOINT_KINDS:
            return bool(self.endpoint)
        # Not a built-in kind — a dynamically-loaded plugin (ROADMAP.md 0.9.0). Deferred
        # import: `plugins.py` imports this module for `TRANSLATION_PROVIDER_KINDS`, so
        # importing it back at module level here would be circular.
        from legendarr_backend.subtitle_translation.plugins import (
            plugin_required_credential_fields,
        )

        required = plugin_required_credential_fields(self.kind)
        if required:
            return all(getattr(self, field, None) for field in required)
        return True

    @property
    def is_configured(self) -> bool:
        """Whether the enable toggle should be available at all. Every kind in this catalog
        needs a credential, so this mirrors `has_credentials` — there's no reachability-only
        kind yet (unlike `SubtitleProviderConfig`)."""
        return self.has_credentials

    @property
    def label(self) -> str:
        """Display name for this row's `kind` — built-in or plugin-supplied
        (ROADMAP.md 0.9.0). Deferred import, same reason as `has_credentials`'s."""
        from legendarr_backend.subtitle_translation.provider_catalog import provider_label

        return provider_label(self.kind)

    @property
    def credential_fields(self) -> tuple[str, ...]:
        """Which config field(s) this row's `kind` edit form should render — built-in or
        plugin-supplied. Deferred import, same reason as `has_credentials`'s."""
        from legendarr_backend.subtitle_translation.provider_catalog import (
            provider_credential_fields,
        )

        return provider_credential_fields(self.kind)


class TranslationAttempt(SQLModel, table=True):
    """Append-only record of one successful translation — the Statistics view's data
    source for "translated ... over time, per profile and provider" (ROADMAP.md 0.20.0),
    mirroring `subtitle_acquisition.models.AcquisitionAttempt`'s shape and role for the
    acquisition side.

    Written by `translate_media_file.translate_media_file` once per target language it
    successfully translates — never for a skipped/failed target, same as
    `AcquisitionAttempt` only records the winning candidate, not every rejected one.
    `subtitle_id` points at the target `Subtitle` row (not unique — a target can be
    retranslated later, e.g. after its source changes, so its full history survives
    instead of being overwritten).
    """

    id: int | None = Field(default=None, primary_key=True)
    subtitle_id: int = Field(foreign_key="subtitle.id", index=True, ondelete="CASCADE")
    provider: str
    source_language: str
    target_language: str
    translated_at: datetime
