import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from apscheduler.events import (
    EVENT_JOB_ADDED,
    EVENT_JOB_ERROR,
    EVENT_JOB_MODIFIED,
    JobEvent,
    JobExecutionEvent,
)
from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger(__name__)

# How many backed-off re-enqueues a one-off job gets after its own in-process
# `with_retry` attempts are exhausted, and how long to wait before each one. Beyond
# this the failure just stands, same as before this module existed.
MAX_SCHEDULE_RETRIES = 3
BACKOFF_SCHEDULE = [timedelta(minutes=2), timedelta(minutes=5), timedelta(minutes=15)]


@dataclass(frozen=True)
class _CachedJob:
    func: Callable[[], None]
    name: str
    executor: str


class ScheduledRetryRegistry:
    """Re-enqueues a one-off (`"date"`-triggered) job for a later attempt when it fails
    outright, instead of letting that failure be the last anyone hears of it.

    Builds on top of `scheduling/retry.py`'s `with_retry`, which only retries inside a
    single execution: a handful of quick, fixed-delay attempts on the same executor
    thread. Once those are exhausted the job still fails — this registry is what turns
    that failure into a follow-up run a few minutes later instead of a dead end.

    A one-off job is already gone from the jobstore by the time its `EVENT_JOB_ERROR`
    fires — same problem `RunningTaskRegistry`/`JobHistoryRecorder` solve for
    name/queue (`scheduling/running_tasks.py`, `system/job_history.py`) — so the job's
    callable is cached here too, off `EVENT_JOB_ADDED`/`EVENT_JOB_MODIFIED`, and reused
    to `add_job` a fresh one-shot run at a backed-off time. A periodic job is still
    present in the jobstore when it errors (`scheduler.get_job` returns non-`None`) and
    already gets a natural retry at its next tick, so it's left alone here.

    Bounded by `MAX_SCHEDULE_RETRIES`. The attempt counter resets whenever a fresh
    enqueue of the same `job_id` is observed — including a user re-triggering the same
    action (e.g. clicking "Translate" again) while a backed-off retry is still pending
    — so that starts its own budget instead of inheriting a stale one. Submission and
    completion can arrive from different threads, so access is locked.
    """

    def __init__(self) -> None:
        self._jobs: dict[str, _CachedJob] = {}
        self._attempts: dict[str, int] = {}
        self._lock = threading.Lock()

    def remember(self, event: JobEvent, scheduler: BackgroundScheduler) -> None:
        job = scheduler.get_job(event.job_id)
        if job is None:
            return
        with self._lock:
            self._jobs[event.job_id] = _CachedJob(
                func=job.func, name=job.name, executor=job.executor
            )
            self._attempts.pop(event.job_id, None)

    def handle_error(self, event: JobExecutionEvent, scheduler: BackgroundScheduler) -> None:
        if scheduler.get_job(event.job_id) is not None:
            # Still in the jobstore — a periodic job, whose next tick is already a retry.
            return
        with self._lock:
            cached = self._jobs.get(event.job_id)
            if cached is None:
                return
            attempt = self._attempts.get(event.job_id, 0)
            if attempt >= MAX_SCHEDULE_RETRIES:
                logger.warning(
                    "%s exhausted %d scheduled retries, giving up",
                    event.job_id,
                    MAX_SCHEDULE_RETRIES,
                )
                self._jobs.pop(event.job_id, None)
                self._attempts.pop(event.job_id, None)
                return

        run_date = datetime.now(UTC) + BACKOFF_SCHEDULE[attempt]
        logger.warning(
            "%s failed, scheduling retry %d/%d at %s",
            event.job_id,
            attempt + 1,
            MAX_SCHEDULE_RETRIES,
            run_date,
        )
        scheduler.add_job(
            cached.func,
            "date",
            run_date=run_date,
            id=event.job_id,
            name=cached.name,
            executor=cached.executor,
            max_instances=1,
            replace_existing=True,
            misfire_grace_time=None,
        )
        # `add_job` above just fired `EVENT_JOB_ADDED` synchronously (nothing existed to
        # replace), which ran `remember()` and reset the counter it just cached — overwrite
        # it with the real attempt count now that the reschedule has actually happened.
        with self._lock:
            self._attempts[event.job_id] = attempt + 1

    def clear(self) -> None:
        with self._lock:
            self._jobs.clear()
            self._attempts.clear()


_registry = ScheduledRetryRegistry()


def attach_scheduled_retry(scheduler: BackgroundScheduler) -> None:
    """Wire the shared registry onto `scheduler`'s event stream.

    Call once per scheduler instance, alongside `attach_running_task_registry`/
    `attach_job_history_recorder` (`legendarr_backend/bootstrap.py`).
    """
    scheduler.add_listener(
        lambda event: _registry.remember(event, scheduler), EVENT_JOB_ADDED | EVENT_JOB_MODIFIED
    )
    scheduler.add_listener(lambda event: _registry.handle_error(event, scheduler), EVENT_JOB_ERROR)


def reset_scheduled_retries() -> None:
    """Clear all in-memory scheduled-retry state. For test isolation only."""
    _registry.clear()
