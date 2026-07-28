from fastapi import APIRouter, Request

from legendarr_backend.config.settings import get_settings
from legendarr_backend.settings.manage_settings import get_task_settings, update_task_settings
from legendarr_backend.settings.schemas import TaskSettings

router = APIRouter(prefix="/settings")


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
