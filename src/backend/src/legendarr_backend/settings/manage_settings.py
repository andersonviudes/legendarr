import logging

from apscheduler.schedulers.background import BackgroundScheduler

from legendarr_backend.config.config_file import (
    load_or_create_config_file,
    update_config_file,
)
from legendarr_backend.config.settings import Settings
from legendarr_backend.media_library.jobs import (
    register_history_poll_job,
    register_scan_job,
    register_sync_job,
)
from legendarr_backend.settings.schemas import (
    BackupSettings,
    GeneralSettings,
    TaskSettings,
    TranslationDefaultsSettings,
    WebhookSettings,
)

logger = logging.getLogger(__name__)


def get_task_settings(settings: Settings) -> TaskSettings:
    """Read the current task settings from `config.yaml` (fresh from disk)."""
    config = load_or_create_config_file(settings)
    return TaskSettings.model_validate(config.model_dump())


def update_task_settings(
    settings: Settings,
    update: TaskSettings,
    scheduler: BackgroundScheduler | None = None,
) -> TaskSettings:
    """Persist task settings to `config.yaml` and, when a scheduler is running,
    re-register the three interval jobs with the new policy.

    Re-registering replaces each job wholesale (`replace_existing=True`), applying
    the new trigger, retry wrapper and concurrency policy at once — the interval
    countdown restarts from the save, and pending ad-hoc scans keep the policy they
    were enqueued with. Without a scheduler (backend run standalone) the change is
    still persisted and takes effect on the next start.
    """
    config = update_config_file(settings, update.model_dump())
    if scheduler is not None:
        register_sync_job(scheduler, config)
        register_scan_job(scheduler, config)
        register_history_poll_job(scheduler, config)
        logger.info("task settings updated and scheduled jobs re-registered")
    else:
        logger.info("task settings updated (no running scheduler; applies on next start)")
    return TaskSettings.model_validate(config.model_dump())


def get_translation_defaults(settings: Settings) -> TranslationDefaultsSettings:
    """Read the current translation-provider default from `config.yaml` (fresh from disk)."""
    config = load_or_create_config_file(settings)
    return TranslationDefaultsSettings.model_validate(config.model_dump())


def update_translation_defaults(
    settings: Settings, update: TranslationDefaultsSettings
) -> TranslationDefaultsSettings:
    """Persist the translation-provider default to `config.yaml`.

    No scheduler involvement (unlike task settings) — `resolve_provider_chain` reads it
    fresh at each translation run, there's nothing to re-register.
    """
    config = update_config_file(settings, update.model_dump())
    return TranslationDefaultsSettings.model_validate(config.model_dump())


def get_webhook_settings(settings: Settings) -> WebhookSettings:
    """Read the current webhook base URL from `config.yaml` (fresh from disk)."""
    config = load_or_create_config_file(settings)
    return WebhookSettings.model_validate(config.model_dump())


def update_webhook_settings(settings: Settings, update: WebhookSettings) -> WebhookSettings:
    """Persist the webhook base URL to `config.yaml`.

    No scheduler involvement (unlike task settings) — the Arr Services page reads it
    fresh at render time, there's nothing to re-register.
    """
    config = update_config_file(settings, update.model_dump())
    return WebhookSettings.model_validate(config.model_dump())


def get_general_settings(settings: Settings) -> GeneralSettings:
    """Read the current UI locale from `config.yaml` (fresh from disk)."""
    config = load_or_create_config_file(settings)
    return GeneralSettings.model_validate(config.model_dump())


def update_general_settings(settings: Settings, update: GeneralSettings) -> GeneralSettings:
    """Persist the UI locale to `config.yaml`.

    No scheduler involvement — `legendarr_web` reads it fresh on every request, there's
    nothing to re-register.
    """
    config = update_config_file(settings, update.model_dump())
    return GeneralSettings.model_validate(config.model_dump())


def get_backup_settings(settings: Settings) -> BackupSettings:
    """Read the current backup-retention count from `config.yaml` (fresh from disk)."""
    config = load_or_create_config_file(settings)
    return BackupSettings.model_validate(config.model_dump())


def update_backup_settings(settings: Settings, update: BackupSettings) -> BackupSettings:
    """Persist the backup-retention count to `config.yaml`.

    No scheduler involvement — `backup.manage_backups.create_backup` reads it fresh at
    each run, there's nothing to re-register.
    """
    config = update_config_file(settings, update.model_dump())
    return BackupSettings.model_validate(config.model_dump())
