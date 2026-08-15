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
        return True

    @property
    def is_configured(self) -> bool:
        """Whether the enable toggle should be available at all. Every kind in this catalog
        needs a credential, so this mirrors `has_credentials` — there's no reachability-only
        kind yet (unlike `SubtitleProviderConfig`)."""
        return self.has_credentials
