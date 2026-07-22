from typing import Literal

from sqlalchemy import Column
from sqlmodel import Field, SQLModel

from legendarr_backend.security.encrypted_string import EncryptedString

SUBTITLE_PROVIDER_KINDS = (
    "opensubtitles",
    "addic7ed",
    "yify_subtitles",
    "subdl",
    "tvsubtitles",
    "legendas_net",
    "napiprojekt",
    "subsource",
    "animetosho",
    "supersubtitles",
    "animekalesi",
    "greeksubtitles",
    "betaseries",
)

# Derived from the tuple above rather than hand-duplicated, so the two can't drift apart.
SubtitleProviderKind = Literal[*SUBTITLE_PROVIDER_KINDS]

# Which credential(s) each kind needs to be usable — mirrors the `_require()` checks in
# `connection_tests.py`. A kind in neither set needs no credential at all, so it's always
# considered configured.
_API_KEY_KINDS = {"opensubtitles", "subdl", "subsource", "betaseries"}
_USERNAME_PASSWORD_KINDS = {"addic7ed", "legendas_net"}


class SubtitleProviderConfig(SQLModel, table=True):
    """Registration/credentials for one of the fixed `SUBTITLE_PROVIDER_KINDS`.

    The catalog is fixed (one row per kind, seeded at startup) rather than user-created
    like `ArrService` — providers authenticate one of three ways (api_key only, username
    + password, or no credential at all), so a row only ever populates the field(s) its
    kind needs and leaves the rest `None`.
    """

    id: int | None = Field(default=None, primary_key=True)
    kind: str = Field(index=True, unique=True)
    enabled: bool = Field(default=True)
    api_key: str | None = Field(default=None, sa_column=Column(EncryptedString))
    username: str | None = Field(default=None)
    password: str | None = Field(default=None, sa_column=Column(EncryptedString))
    connection_verified: bool = Field(default=False)
    # OpenSubtitles-only search options — defaults mirror Bazarr's opensubtitlescom
    # provider (use_hash=True, both "include ..." flags default off, since the API
    # itself excludes AI/machine-translated results unless asked to include them).
    # Search isn't built yet, so nothing reads these back out — this only saves them.
    # Ignored (left at their default) for every other kind.
    use_hash: bool = Field(default=True)
    include_ai_translated: bool = Field(default=False)
    include_machine_translated: bool = Field(default=False)

    @property
    def has_credentials(self) -> bool:
        """Whether this provider has the credential(s) its kind needs — the web UI uses
        this to gate the enable toggle so a provider can't be switched on before it's
        actually usable."""
        if self.kind in _API_KEY_KINDS:
            return bool(self.api_key)
        if self.kind in _USERNAME_PASSWORD_KINDS:
            return bool(self.username and self.password)
        return True

    @property
    def is_configured(self) -> bool:
        """Whether the enable toggle should be available at all. A credentialed provider
        needs its credential(s) set; one with no credential concept has nothing to set, so
        it instead needs at least one successful "Test connection" — otherwise it'd be
        enabled from the moment it's seeded, with nothing ever having confirmed it works."""
        if self.kind in _API_KEY_KINDS or self.kind in _USERNAME_PASSWORD_KINDS:
            return self.has_credentials
        return self.connection_verified
