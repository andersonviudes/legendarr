from datetime import datetime
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
# `connection_tests.py`. A kind in neither set needs no *required* credential, so it's
# always considered configured (once a successful "Test connection" confirms it, for a
# kind with no credential concept at all — see `is_configured` below).
# "animetosho" isn't here even though `api_key` is a real, usable field for it — its
# `api_key` (an AniDB HTTP API client key) is optional, not required: search still
# works without one via a heuristic filename match (see `providers/animetosho.py`'s
# `_search_by_anime_id`), just less precisely than the exact-episode-id path a key
# unlocks. So it's grouped with the no-credential kinds here on purpose.
_API_KEY_KINDS = {"subdl", "subsource", "betaseries"}
# OpenSubtitles' "API key" identifies the calling *application*, not the user — it's
# hardcoded in `providers/opensubtitles.py` rather than stored per-row, so this kind
# authenticates with the user's own username/password (via a real `/login` call) like
# Addic7ed/legendas.net, not the generic single-secret shape.
_USERNAME_PASSWORD_KINDS = {"addic7ed", "legendas_net", "opensubtitles"}


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
    # Which registered `SubtitleProxy` (if any) this provider's requests should go through —
    # e.g. a FlareSolverr instance for a CAPTCHA/Cloudflare-gated kind. Nullable: most kinds
    # don't need one. `ondelete="SET NULL"` so deleting a proxy just unassigns it here instead
    # of blocking the delete or cascading.
    proxy_id: int | None = Field(
        default=None, foreign_key="subtitleproxy.id", index=True, ondelete="SET NULL"
    )
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

    @property
    def credentials_required(self) -> bool:
        """Whether this kind can't be enabled without a credential — the web UI uses this
        to decide between "Requires credentials" and "No credentials needed"/"Run test to
        enable" on the provider list. Same two groups as `is_configured` above: `animetosho`
        has a real `api_key` field but isn't in either group (it's optional), so this is
        `False` for it just like a true no-credential kind."""
        return self.kind in _API_KEY_KINDS or self.kind in _USERNAME_PASSWORD_KINDS


class AcquiredSubtitle(SQLModel, table=True):
    """Acquisition provenance for a `Subtitle` row that came from a provider download —
    written by `acquire_subtitle_for_media_file` (automatic) and
    `download_subtitle_candidate` (manual search), never for an embedded, manually
    uploaded, or translated subtitle. One-to-one with `Subtitle`: `subtitle_id` stays
    the same across an in-place content rewrite at the same external sidecar path
    (see `scan_media_subtitles.py`), so `upgrade_subtitle_for_media_file` updates this
    row in place rather than inserting a second one.

    `score` is the `match_score.score_candidate` result at acquisition/upgrade time —
    what a later upgrade pass compares a fresh candidate's score against.
    """

    id: int | None = Field(default=None, primary_key=True)
    subtitle_id: int = Field(foreign_key="subtitle.id", unique=True, index=True, ondelete="CASCADE")
    provider: str
    release_name: str
    download_id: str
    score: float
    acquired_at: datetime


class AcquisitionAttempt(SQLModel, table=True):
    """Append-only audit trail entry for one winning acquisition/upgrade/manual-download
    pick — ROADMAP.md 0.12.0's structured audit trail. Unlike `AcquiredSubtitle` (the
    current-state row, upserted in place), a new row is inserted here every time
    `record_acquired_subtitle` runs, so a subtitle's full acquisition history survives
    an upgrade instead of being overwritten.

    `*_matched` is `None` when the reference filename had no detectable value for that
    attribute (nothing to compare, excluded from `score`/`title_similarity` the same
    way `match_score.evaluate_candidate` excludes it), `True`/`False` otherwise —
    mirrors `match_score.ATTRIBUTE_WEIGHTS`'s five attributes.

    `replaced_attempt_id` points at the previous attempt for the same `subtitle_id`
    (`None` on a subtitle's first-ever acquisition) — the link from an upgraded
    subtitle back to the one it replaced.
    """

    id: int | None = Field(default=None, primary_key=True)
    subtitle_id: int = Field(foreign_key="subtitle.id", index=True, ondelete="CASCADE")
    provider: str
    release_name: str
    download_id: str
    score: float
    title_similarity: float
    resolution_matched: bool | None = Field(default=None)
    source_matched: bool | None = Field(default=None)
    codec_matched: bool | None = Field(default=None)
    release_group_matched: bool | None = Field(default=None)
    edition_matched: bool | None = Field(default=None)
    replaced_attempt_id: int | None = Field(
        default=None, foreign_key="acquisitionattempt.id", ondelete="SET NULL"
    )
    attempted_at: datetime


class SubtitleBlacklistEntry(SQLModel, table=True):
    """A subtitle a user has flagged as bad for one `MediaFile`/language, so it's never
    reused or re-fetched for that media item again.

    `origin` is `"acquired"` (a provider download — `provider`/`release_name`/
    `download_id` identify the exact release to exclude from future search results,
    same fields `AcquiredSubtitle` records) or `"translated"` (a translation output —
    the three provider fields stay `None`, since there's no candidate list to filter;
    instead its mere presence blocks the periodic translation job from regenerating
    that target language, see `subtitle_translation/translate_media_file.py`).
    """

    id: int | None = Field(default=None, primary_key=True)
    media_file_id: int = Field(foreign_key="mediafile.id", index=True, ondelete="CASCADE")
    language: str
    # Plain `str`, not a `Literal["acquired", "translated"]` — same reasoning as
    # `SubtitleProviderConfig.kind` above: SQLModel maps the table column from the
    # annotation's bare type, so callers (`manage_subtitle_blacklist.py`) validate the
    # two accepted values in Python rather than the schema itself.
    origin: str
    provider: str | None = Field(default=None)
    release_name: str | None = Field(default=None)
    download_id: str | None = Field(default=None)
    blacklisted_at: datetime


class AcquisitionFailure(SQLModel, table=True):
    """Append-only record of one acquisition search where at least one configured
    provider raised — ROADMAP.md 0.20.0's History view "error status" data source,
    mirroring `subtitle_translation.models.TranslationFailure`'s shape and role for
    the translation side.

    Written by `acquire_media_file_subtitle._search_and_download` only when its
    provider loop is fully exhausted *and* saw at least one exception — a clean "no
    provider found an above-cutoff match" pass (zero exceptions) is a common,
    non-error outcome (see `AcquisitionResult.skipped_reason`) and never reaches here.
    `media_file_id` (not `subtitle_id`, unlike `AcquisitionAttempt`): a failed search
    never produces an `AcquiredSubtitle`/`Subtitle` row to point at.
    """

    id: int | None = Field(default=None, primary_key=True)
    media_file_id: int = Field(foreign_key="mediafile.id", index=True, ondelete="CASCADE")
    language: str
    error_message: str
    failed_at: datetime
