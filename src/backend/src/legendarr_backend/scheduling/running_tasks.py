import threading
from dataclasses import dataclass
from datetime import datetime

from apscheduler.events import (
    EVENT_JOB_ADDED,
    EVENT_JOB_ERROR,
    EVENT_JOB_EXECUTED,
    EVENT_JOB_MISSED,
    EVENT_JOB_MODIFIED,
    EVENT_JOB_SUBMITTED,
    JobEvent,
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

    One-off jobs — every manual "Sync Now"/"Scan Disk"/translate/acquire trigger, all
    `"date"`-triggered — are already gone from the jobstore by the time `EVENT_JOB_SUBMITTED`
    fires, so `scheduler.get_job()` returns `None` right when `submit()` would need it.
    `remember()` caches each job's name/executor off `EVENT_JOB_ADDED`/`EVENT_JOB_MODIFIED`
    for that case. Periodic jobs go the other way: they're registered *before*
    `scheduler.start()` (`legendarr_backend/bootstrap.py`), and APScheduler doesn't dispatch
    `EVENT_JOB_ADDED` for a stopped scheduler, so the cache is never populated for them — but
    they're still in the jobstore at submit time, so `scheduler.get_job()` works fine there.
    `submit()` tries the live lookup first and only falls back to the cache.
    """

    def __init__(self) -> None:
        self._tasks: dict[tuple[str, datetime], RunningTask] = {}
        self._job_meta: dict[str, tuple[str, str]] = {}
        self._lock = threading.Lock()

    def remember(self, event: JobEvent, scheduler: BackgroundScheduler) -> None:
        job = scheduler.get_job(event.job_id)
        if job is None:
            return
        with self._lock:
            self._job_meta[event.job_id] = (job.name, job.executor)

    def submit(self, event: JobSubmissionEvent, scheduler: BackgroundScheduler) -> None:
        job = scheduler.get_job(event.job_id)
        if job is not None:
            name, queue = job.name, job.executor
        else:
            with self._lock:
                meta = self._job_meta.get(event.job_id)
            if meta is None:
                return
            name, queue = meta
        with self._lock:
            for run_time in event.scheduled_run_times:
                self._tasks[(event.job_id, run_time)] = RunningTask(
                    job_id=event.job_id,
                    name=name,
                    queue=queue,
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
            self._job_meta.clear()


_registry = RunningTaskRegistry()


def attach_running_task_registry(scheduler: BackgroundScheduler) -> None:
    """Wire the shared registry onto `scheduler`'s event stream.

    Call once per scheduler instance, alongside where its periodic jobs are registered
    (`legendarr_backend/bootstrap.py`).
    """
    scheduler.add_listener(
        lambda event: _registry.remember(event, scheduler), EVENT_JOB_ADDED | EVENT_JOB_MODIFIED
    )
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
