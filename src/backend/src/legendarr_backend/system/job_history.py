import threading
from dataclasses import dataclass
from datetime import UTC, datetime

from apscheduler.events import (
    EVENT_JOB_ADDED,
    EVENT_JOB_ERROR,
    EVENT_JOB_EXECUTED,
    EVENT_JOB_MISSED,
    EVENT_JOB_MODIFIED,
    JobEvent,
    JobExecutionEvent,
)
from apscheduler.schedulers.background import BackgroundScheduler
from sqlmodel import col, select

from legendarr_backend.database.engine import get_session
from legendarr_backend.system.models import JobRun


@dataclass(frozen=True)
class _JobMeta:
    name: str
    queue: str


class JobHistoryRecorder:
    """Persists the outcome of every scheduler job execution, so the System page can show
    history past what's currently running — `RunningTaskRegistry`
    (`scheduling/running_tasks.py`) this mirrors is in-memory and live-only, so it has
    nothing left to show once a job finishes or the process restarts.

    Same job-metadata-caching problem `RunningTaskRegistry` solves: a one-off
    (`"date"`-triggered) job is already gone from the jobstore by the time its completion
    event fires, so `scheduler.get_job()` can't be relied on there — cache name/queue off
    `EVENT_JOB_ADDED`/`EVENT_JOB_MODIFIED` the same way.
    """

    def __init__(self) -> None:
        self._job_meta: dict[str, _JobMeta] = {}
        self._lock = threading.Lock()

    def remember(self, event: JobEvent, scheduler: BackgroundScheduler) -> None:
        job = scheduler.get_job(event.job_id)
        if job is None:
            return
        with self._lock:
            self._job_meta[event.job_id] = _JobMeta(name=job.name, queue=job.executor)

    def record(
        self, event: JobExecutionEvent, scheduler: BackgroundScheduler, *, status: str
    ) -> None:
        job = scheduler.get_job(event.job_id)
        if job is not None:
            name, queue = job.name, job.executor
        else:
            with self._lock:
                meta = self._job_meta.get(event.job_id)
            name, queue = (meta.name, meta.queue) if meta is not None else (event.job_id, "unknown")
        error_message = str(event.exception) if status == "failure" and event.exception else None
        with get_session() as session:
            session.add(
                JobRun(
                    job_id=event.job_id,
                    name=name,
                    queue=queue,
                    status=status,
                    started_at=event.scheduled_run_time,
                    finished_at=datetime.now(UTC),
                    error_message=error_message,
                )
            )
            session.commit()


_recorder = JobHistoryRecorder()


def attach_job_history_recorder(scheduler: BackgroundScheduler) -> None:
    """Wire the shared recorder onto `scheduler`'s event stream.

    Call once per scheduler instance, alongside `attach_running_task_registry`
    (`legendarr_backend/bootstrap.py`).
    """
    scheduler.add_listener(
        lambda event: _recorder.remember(event, scheduler), EVENT_JOB_ADDED | EVENT_JOB_MODIFIED
    )
    scheduler.add_listener(
        lambda event: _recorder.record(event, scheduler, status="success"), EVENT_JOB_EXECUTED
    )
    scheduler.add_listener(
        lambda event: _recorder.record(event, scheduler, status="failure"), EVENT_JOB_ERROR
    )
    scheduler.add_listener(
        lambda event: _recorder.record(event, scheduler, status="missed"), EVENT_JOB_MISSED
    )


def list_job_runs(limit: int = 20) -> list[JobRun]:
    """Return the most recently finished job runs, newest first."""
    with get_session() as session:
        return list(
            session.exec(select(JobRun).order_by(col(JobRun.finished_at).desc()).limit(limit))
        )
