import threading
from dataclasses import dataclass
from datetime import datetime

from apscheduler.events import (
    EVENT_JOB_ERROR,
    EVENT_JOB_EXECUTED,
    EVENT_JOB_MISSED,
    EVENT_JOB_SUBMITTED,
    JobExecutionEvent,
    JobSubmissionEvent,
)
from apscheduler.schedulers.background import BackgroundScheduler


@dataclass(frozen=True)
class RunningTask:
    job_id: str
    name: str
    queue: str
    started_at: datetime


class RunningTaskRegistry:
    """Tracks jobs currently handed to an executor, keyed by `(job_id, scheduled_run_time)`
    so two concurrent instances of the same job (`max_instances > 1`) don't collide.

    Backs the topbar indicator and the System → Tasks page, so both can show what's
    executing right now without polling the scheduler's own state, which only tracks
    *scheduled* jobs, not in-flight executions. State resets on restart — same as the log
    ring buffer this mirrors (`logging/setup.py`): this is for live status, not a
    post-mortem. Submission and completion events arrive on different threads (the
    scheduler's own timer thread vs. an executor worker thread), so access is locked.
    """

    def __init__(self) -> None:
        self._tasks: dict[tuple[str, datetime], RunningTask] = {}
        self._lock = threading.Lock()

    def submit(self, event: JobSubmissionEvent, scheduler: BackgroundScheduler) -> None:
        job = scheduler.get_job(event.job_id)
        if job is None:
            return
        with self._lock:
            for run_time in event.scheduled_run_times:
                self._tasks[(event.job_id, run_time)] = RunningTask(
                    job_id=event.job_id,
                    name=job.name,
                    queue=job.executor,
                    started_at=datetime.now(),
                )

    def finish(self, event: JobExecutionEvent) -> None:
        with self._lock:
            self._tasks.pop((event.job_id, event.scheduled_run_time), None)

    def tasks(self) -> list[RunningTask]:
        with self._lock:
            return list(self._tasks.values())

    def clear(self) -> None:
        with self._lock:
            self._tasks.clear()


_registry = RunningTaskRegistry()


def attach_running_task_registry(scheduler: BackgroundScheduler) -> None:
    """Wire the shared registry onto `scheduler`'s event stream.

    Call once per scheduler instance, alongside where its periodic jobs are registered
    (`legendarr_backend/bootstrap.py`).
    """
    scheduler.add_listener(lambda event: _registry.submit(event, scheduler), EVENT_JOB_SUBMITTED)
    scheduler.add_listener(
        _registry.finish, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR | EVENT_JOB_MISSED
    )


def get_running_tasks() -> list[RunningTask]:
    """Return the tasks currently handed to an executor, i.e. genuinely running."""
    return _registry.tasks()


def reset_running_tasks() -> None:
    """Clear the in-memory running-task state. For test isolation only."""
    _registry.clear()
