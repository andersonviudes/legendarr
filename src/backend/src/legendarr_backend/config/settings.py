from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for legendarr, sourced from environment variables."""

    model_config = SettingsConfigDict(env_prefix="LEGENDARR_", env_file=".env")

    data_dir: Path = Field(default=Path("./data"))
    database_url: str = Field(default="")
    secret_key: str = Field(default="")
    radarr_url: str = Field(default="")
    radarr_api_key: str = Field(default="")
    sonarr_url: str = Field(default="")
    sonarr_api_key: str = Field(default="")
    # The externally-reachable address of this legendarr instance, e.g.
    # "https://legendarr.example.com" — used to build the Radarr/Sonarr webhook URL
    # shown on the Arr Services settings page. Empty means "not configured yet"; the
    # page then shows the relative webhook path with a hint instead.
    public_url: str = Field(default="")
    sync_interval_minutes: int = Field(default=15)
    sync_retry_attempts: int = Field(default=3, ge=1)
    sync_retry_delay_seconds: float = Field(default=5.0)
    sync_max_instances: int = Field(default=1)
    sync_coalesce: bool = Field(default=True)
    scan_interval_minutes: int = Field(default=60)
    scan_retry_attempts: int = Field(default=3, ge=1)
    scan_retry_delay_seconds: float = Field(default=5.0)
    scan_max_instances: int = Field(default=1)
    scan_coalesce: bool = Field(default=True)
    history_poll_interval_minutes: int = Field(default=15)
    history_poll_retry_attempts: int = Field(default=3, ge=1)
    history_poll_retry_delay_seconds: float = Field(default=5.0)
    history_poll_max_instances: int = Field(default=1)
    history_poll_coalesce: bool = Field(default=True)
    subtitle_scan_interval_minutes: int = Field(default=60)
    subtitle_scan_retry_attempts: int = Field(default=3, ge=1)
    subtitle_scan_retry_delay_seconds: float = Field(default=5.0)
    subtitle_scan_max_instances: int = Field(default=1)
    subtitle_scan_coalesce: bool = Field(default=True)
    # How long a `MediaFile` whose size hasn't changed goes without being re-probed by the
    # subtitle scan fan-out — re-probing (ffprobe/extraction) on every interval tick is
    # wasted work when nothing changed, but a manually-dropped external subtitle still
    # needs to be picked up eventually without touching the video file at all.
    subtitle_scan_recheck_hours: int = Field(default=24)
    # ffprobe/ffmpeg subprocess timeout for embedded subtitle-track probing/extraction
    # (ROADMAP.md 0.6.0), guarding against a hung/corrupt container.
    embedded_subtitle_probe_timeout_seconds: float = Field(default=30.0)
    # Per-cue Tesseract OCR timeout for a PGS embedded track (ROADMAP.md 0.14.0), passed
    # as `pytesseract`'s own `timeout=` — a differently-shaped subprocess call than
    # `embedded_subtitle_probe_timeout_seconds`'s single ffprobe/ffmpeg run, so it gets its
    # own setting, same posture as `timing_sync_timeout_seconds` below.
    ocr_cue_timeout_seconds: float = Field(default=10.0)
    translate_retry_attempts: int = Field(default=3, ge=1)
    translate_retry_delay_seconds: float = Field(default=5.0)
    # ROADMAP.md 0.10.0 — periodic translation fan-out, same posture as
    # `subtitle_scan_interval_minutes`: config/env-only, not yet in the runtime-editable
    # Settings UI.
    translate_interval_minutes: int = Field(default=60)
    translate_max_instances: int = Field(default=1)
    translate_coalesce: bool = Field(default=True)
    default_translation_provider: str | None = Field(default=None)
    # ROADMAP.md 0.10.0 — periodic acquisition fan-out, same posture as
    # `translate_interval_minutes` above; acquisition previously took retry policy only as
    # ad-hoc function args (no scheduled job existed yet to need config-driven defaults).
    acquisition_retry_attempts: int = Field(default=3, ge=1)
    acquisition_retry_delay_seconds: float = Field(default=5.0)
    acquisition_interval_minutes: int = Field(default=60)
    acquisition_max_instances: int = Field(default=1)
    acquisition_coalesce: bool = Field(default=True)
    # Subtitle upgrade: re-search providers for an already-acquired subtitle and replace
    # it in place if a strictly better-scoring release is now available (ROADMAP.md
    # 0.12.0's upgrade/replace pass) — its own periodic job (`subtitle_upgrade_fanout`),
    # fully decoupled from `acquisition_*` above: acquisition only searches for what's
    # missing, upgrade only re-checks what's already there, each on its own schedule/queue.
    # Same daily-cadence posture as `metadata_refresh_interval_minutes` below.
    upgrade_interval_minutes: int = Field(default=1440)
    upgrade_retry_attempts: int = Field(default=3, ge=1)
    upgrade_retry_delay_seconds: float = Field(default=5.0)
    upgrade_max_instances: int = Field(default=1)
    upgrade_coalesce: bool = Field(default=True)
    # Manual "sync timing" only (ROADMAP.md 0.7.0), same posture as translate_retry_attempts
    # — no interval/max_instances/coalesce fields, just the retry policy
    # `enqueue_timing_sync` needs. `ffsubsync` decodes the whole audio track, so its timeout
    # defaults higher than `embedded_subtitle_probe_timeout_seconds`.
    timing_sync_retry_attempts: int = Field(default=3, ge=1)
    timing_sync_retry_delay_seconds: float = Field(default=5.0)
    timing_sync_timeout_seconds: float = Field(default=120.0)
    # Manual "refetch metadata" only, same posture as timing_sync_retry_attempts above —
    # no interval/max_instances/coalesce fields, just the retry policy
    # `enqueue_metadata_refetch` needs.
    metadata_refetch_retry_attempts: int = Field(default=3, ge=1)
    metadata_refetch_retry_delay_seconds: float = Field(default=5.0)
    # ROADMAP.md 0.20.0 — periodic metadata refresh, same posture as
    # `translate_interval_minutes`: config/env-only, not yet in the runtime-editable
    # Settings UI. Deliberately independent from `metadata_refetch_retry_attempts`/
    # `metadata_refetch_retry_delay_seconds` above (the manual "Refetch All" button's own
    # policy) rather than sharing them, even though both ultimately call
    # `enqueue_metadata_refetch` — a periodic job failing repeatedly shouldn't be tuned by
    # the same knob as an interactive one-off click. Metadata changes far less often than
    # library contents, so the default is once a day rather than the 15/60 min cadence
    # `sync_*`/`scan_*` use.
    metadata_refresh_interval_minutes: int = Field(default=1440)
    metadata_refresh_retry_attempts: int = Field(default=3, ge=1)
    metadata_refresh_retry_delay_seconds: float = Field(default=5.0)
    metadata_refresh_max_instances: int = Field(default=1)
    metadata_refresh_coalesce: bool = Field(default=True)
    # ROADMAP.md 0.20.0 — periodic local poster-cache cleanup (see
    # `Settings.poster_cache_dir`), its own schedule independent of
    # `metadata_refresh_interval_minutes` above — orphaned files only ever appear when an
    # item leaves the library, not on every metadata refresh. Same config/env-only posture.
    poster_cache_cleanup_interval_minutes: int = Field(default=1440)
    poster_cache_cleanup_retry_attempts: int = Field(default=3, ge=1)
    poster_cache_cleanup_retry_delay_seconds: float = Field(default=5.0)
    poster_cache_cleanup_max_instances: int = Field(default=1)
    poster_cache_cleanup_coalesce: bool = Field(default=True)
    # ROADMAP.md 0.22.0 — periodic sweep of orphaned `.tmp` siblings left behind by a
    # process killed mid-extraction/OCR/transcription/timing-sync (see
    # `maintenance.cleanup_temp_files`). Same config/env-only posture as
    # `poster_cache_cleanup_*` above. `min_age_minutes` must stay above the slowest
    # legitimate writer (`speech_to_text_timeout_seconds`, default 1800s/30min) so a
    # file a still-running job is actively writing is never swept as an orphan.
    temp_file_cleanup_interval_minutes: int = Field(default=1440)
    temp_file_cleanup_retry_attempts: int = Field(default=3, ge=1)
    temp_file_cleanup_retry_delay_seconds: float = Field(default=5.0)
    temp_file_cleanup_max_instances: int = Field(default=1)
    temp_file_cleanup_coalesce: bool = Field(default=True)
    temp_file_cleanup_min_age_minutes: float = Field(default=60.0)
    # ROADMAP.md 0.15.0 — speech-to-text fallback (`faster_whisper`), tried only when a
    # `LanguageProfile.speech_to_text_fallback` profile finds nothing via any other
    # acquisition tier. `model_size` is a global instance-wide choice (same posture as
    # `default_translation_provider` above), not per-profile — trades accuracy for
    # speed/RAM, so one deployment picks one size. The timeout defaults far higher than
    # `timing_sync_timeout_seconds`: transcribing a full movie on CPU can take much
    # longer than `ffsubsync`'s audio-decode-only pass.
    speech_to_text_model_size: str = Field(default="base")
    speech_to_text_timeout_seconds: float = Field(default=1800.0)
    # ROADMAP.md 0.9.0 — comma-separated `module.path:ClassName` entries, each imported
    # at startup by `subtitle_translation.plugins`. Env-var-only by design (not part of
    # `AppConfigFile`/`config.yaml`, not editable from the web Settings UI): this is a
    # code-import path, a different trust boundary than every other runtime value here.
    translation_plugin_packages: str = Field(default="")
    # ROADMAP.md 0.16.0 — single shared admin login gating the web UI, plus an API key
    # for scripts/non-interactive access to the backend API. Off by default so existing
    # installs stay open until an admin opts in from Settings. `auth_password_hash` is a
    # one-way PBKDF2 hash (see `authentication/passwords.py`), never the plaintext
    # password; `auth_api_key` is a bearer secret like `radarr_api_key`/`sonarr_api_key`.
    auth_enabled: bool = Field(default=False)
    auth_username: str = Field(default="")
    auth_password_hash: str = Field(default="")
    auth_api_key: str = Field(default="")
    # ROADMAP.md 0.19.0 — instance-wide UI display language for legendarr_web, unrelated
    # to `SUPPORTED_LANGUAGES` (subtitle content languages). Single shared admin account,
    # so this is one instance-wide preference, same posture as `default_translation_provider`.
    ui_locale: str = Field(default="en")
    # Instance-wide IANA timezone name used to display timestamps across legendarr_web —
    # doesn't affect what's stored (always UTC) or when scheduled jobs run, same posture
    # as `ui_locale` above.
    timezone: str = Field(default="UTC")
    # ROADMAP.md 0.22.0 — how many `backup/` archives to keep in `data_dir/backups/`
    # before the oldest are pruned on the next create. Backup/restore here covers
    # `config.yaml` + the Fernet key file only, not the SQLite database — see
    # `backup/manage_backups.py`.
    backup_retention_count: int = Field(default=7, ge=1)
    # How many jobs each named executor queue (`scheduling/queues.py`'s `JobQueue`) is
    # allowed to run at once — the throttle knobs behind PR #107's periodic subtitle
    # discovery/acquisition/translation fan-outs. Same config/env-only posture as most
    # other scheduling knobs (`translate_max_instances`, `acquisition_max_instances`,
    # ...): no runtime-editable Settings UI yet. Unlike those, these also need a full
    # restart to take effect — `legendarr_backend.bootstrap.build_scheduler()` sizes
    # each queue's `ThreadPoolExecutor` once at startup, it isn't rebuilt when
    # `config.yaml` changes. Defaults mirror `scheduling.queues.QUEUE_WORKERS`.
    sync_queue_workers: int = Field(default=1, ge=1)
    scan_queue_workers: int = Field(default=2, ge=1)
    scan_bulk_queue_workers: int = Field(default=1, ge=1)
    translate_queue_workers: int = Field(default=2, ge=1)
    translate_bulk_queue_workers: int = Field(default=1, ge=1)
    acquire_queue_workers: int = Field(default=2, ge=1)
    acquire_bulk_queue_workers: int = Field(default=1, ge=1)
    timing_sync_queue_workers: int = Field(default=2, ge=1)
    metadata_bulk_queue_workers: int = Field(default=1, ge=1)
    maintenance_queue_workers: int = Field(default=1, ge=1)
    upgrade_bulk_queue_workers: int = Field(default=1, ge=1)

    @property
    def translation_plugin_package_list(self) -> list[str]:
        return [
            entry.strip() for entry in self.translation_plugin_packages.split(",") if entry.strip()
        ]

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{self.data_dir / 'legendarr.db'}"

    @property
    def speech_to_text_model_dir(self) -> Path:
        """Where `faster_whisper` caches downloaded model weights — inside `data_dir` so
        they survive a container recreate instead of being re-downloaded, same volume as
        the sqlite database."""
        return self.data_dir / "whisper_models"

    @property
    def poster_cache_dir(self) -> Path:
        """Where locally-cached `media_metadata` poster images live — inside `data_dir`,
        same posture as `speech_to_text_model_dir`. `legendarr_web` serves this directory
        directly via its own `StaticFiles` mount (ROADMAP.md 0.20.0), so both processes
        resolve it from the same `data_dir`."""
        return self.data_dir / "posters"


@lru_cache
def get_settings() -> Settings:
    return Settings()
