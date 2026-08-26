from fastapi import APIRouter, Request

from legendarr_backend.config.settings import get_settings
from legendarr_backend.settings.manage_settings import (
    get_general_settings,
    get_task_settings,
    get_translation_defaults,
    get_webhook_settings,
    update_general_settings,
    update_task_settings,
    update_translation_defaults,
    update_webhook_settings,
)
from legendarr_backend.settings.schemas import (
    GeneralSettings,
    TaskSettings,
    TranslationDefaultsSettings,
    WebhookSettings,
)

router = APIRouter(prefix="/settings", tags=["Settings"])


@router.get("/tasks")
def read_task_settings() -> TaskSettings:
    return get_task_settings(get_settings())


@router.put("/tasks")
def save_task_settings(update: TaskSettings, request: Request) -> TaskSettings:
    """Persist task settings and re-schedule the jobs on the running scheduler.

    The scheduler is optional state (set by the bootstrap lifespan): when absent —
    e.g. the backend API run standalone — the file is still updated and the new
    values apply on the next start.
    """
    scheduler = getattr(request.app.state, "scheduler", None)
    return update_task_settings(get_settings(), update, scheduler)


@router.get("/translation-defaults")
def read_translation_defaults() -> TranslationDefaultsSettings:
    return get_translation_defaults(get_settings())


@router.put("/translation-defaults")
def save_translation_defaults(update: TranslationDefaultsSettings) -> TranslationDefaultsSettings:
    return update_translation_defaults(get_settings(), update)


@router.get("/webhooks")
def read_webhook_settings() -> WebhookSettings:
    return get_webhook_settings(get_settings())


@router.put("/webhooks")
def save_webhook_settings(update: WebhookSettings) -> WebhookSettings:
    return update_webhook_settings(get_settings(), update)


@router.get("/general")
def read_general_settings() -> GeneralSettings:
    return get_general_settings(get_settings())


@router.put("/general")
def save_general_settings(update: GeneralSettings) -> GeneralSettings:
    return update_general_settings(get_settings(), update)
