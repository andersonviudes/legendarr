import logging
from collections.abc import Iterator

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session

from legendarr_backend.database.engine import get_session
from legendarr_backend.system.browse_directory import list_subdirectories
from legendarr_backend.system.job_history import list_job_runs
from legendarr_backend.system.provider_status import list_provider_health
from legendarr_backend.system.read_logs import list_recent_logs
from legendarr_backend.system.resolve_job_media_title import resolve_job_media_titles
from legendarr_backend.system.running_tasks import list_running_tasks
from legendarr_backend.system.scheduler_status import list_scheduled_jobs
from legendarr_backend.system.schemas import (
    DirectoryListingRead,
    JobRunRead,
    LogLineRead,
    ProviderHealthRead,
    RunningTaskRead,
    ScheduledJobRead,
)

router = APIRouter(prefix="/system", tags=["System"])

_LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
}


def _get_scheduler(request: Request):
    scheduler = getattr(request.app.state, "scheduler", None)
    if scheduler is None:
        raise HTTPException(status_code=503, detail="Scheduler is not running")
    return scheduler


def _get_session() -> Iterator[Session]:
    with get_session() as session:
        yield session


@router.get("/directories", response_model=DirectoryListingRead)
def get_directories(path: str = "/") -> DirectoryListingRead:
    try:
        return list_subdirectories(path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Directory not found") from exc
    except NotADirectoryError as exc:
        raise HTTPException(status_code=422, detail="Path is not a directory") from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail="Permission denied") from exc


@router.get("/logs", response_model=list[LogLineRead])
def get_logs(level: str | None = None, limit: int = 200) -> list[LogLineRead]:
    min_level = None
    if level is not None:
        try:
            min_level = _LOG_LEVELS[level.upper()]
        except KeyError as exc:
            raise HTTPException(status_code=422, detail="Unknown log level") from exc
    return list_recent_logs(min_level=min_level, limit=limit)


@router.get("/tasks/running", response_model=list[RunningTaskRead])
def get_running_tasks(session: Session = Depends(_get_session)) -> list[RunningTaskRead]:
    return list_running_tasks(session)


@router.get("/jobs/scheduled", response_model=list[ScheduledJobRead])
def get_scheduled_jobs(request: Request) -> list[ScheduledJobRead]:
    return list_scheduled_jobs(_get_scheduler(request))


@router.get("/jobs/history", response_model=list[JobRunRead])
def get_job_history(limit: int = 20, session: Session = Depends(_get_session)) -> list[JobRunRead]:
    runs = list_job_runs(limit=limit)
    display_names = resolve_job_media_titles(session, (run.job_id for run in runs))
    return [
        JobRunRead(
            job_id=run.job_id,
            name=display_names.get(run.job_id, run.name),
            queue=run.queue,
            status=run.status,
            started_at=run.started_at,
            finished_at=run.finished_at,
            error_message=run.error_message,
        )
        for run in runs
    ]


@router.get("/providers", response_model=list[ProviderHealthRead])
def get_provider_health(session: Session = Depends(_get_session)) -> list[ProviderHealthRead]:
    return list_provider_health(session)
