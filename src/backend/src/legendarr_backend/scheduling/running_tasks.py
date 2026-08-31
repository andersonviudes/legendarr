import threading
from dataclasses import dataclass, replace
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

from legendarr_backend.scheduling.queues import QUEUE_WORKERS, JobQueue


@dataclass(frozen=True)
class RunningTask:
    job_id: str
    name: str
    queue: str
    started_at: datetime
    # Set by `tasks()`, not by `submit()` — see `RunningTaskRegistry.tasks()`. A job is
    # "submitted" to its executor the instant APScheduler sees it's due, regardless of
    # whether a worker thread is actually free; for a queue whose worker count is smaller
    # than a burst of same-queue jobs (every `_bulk` queue is deliberately `max_workers=1`,
    # `scheduling/queues.py`), most of that burst just sits in the executor's own FIFO
    # queue. `queued=True` marks one of those — it hasn't started executing yet, so its
    # `started_at` is really "submitted at", not a real elapsed-time anchor.
    queued: bool = False
    # Live-progress fields (ROADMAP 0.20.0's "Live progress") — all unset until the
    # running job's own code reports a checkpoint via `report_progress()`. `phase` is a
    # domain-defined string ("translating", "searching", ...) the caller picks; this
    # module has no opinion on what phases exist.
    phase: str | None = None
    current_step: int | None = None
    total_steps: int | None = None
    language: str | None = None
    provider: str | None = None


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

    `submit()` records every submission, but a queue whose worker count is smaller than
    a burst of same-queue jobs (any `_bulk` queue, see `scheduling/queues.py`) can end up
    with far more `_tasks` entries than it can actually run at once — the rest are just
    waiting their turn in that executor's own FIFO queue. `tasks()` is what tells the two
    apart (see its own docstring); this class only tracks "submitted", not "started".
    """

    def __init__(self, queue_workers: dict[JobQueue, int] | None = None) -> None:
        self._tasks: dict[tuple[str, datetime], RunningTask] = {}
        self._job_meta: dict[str, tuple[str, str]] = {}
        self._queue_workers: dict[JobQueue, int] = (
            queue_workers if queue_workers is not None else QUEUE_WORKERS
        )
        self._lock = threading.Lock()

    def configure(self, queue_workers: dict[JobQueue, int]) -> None:
        """Override the per-queue worker counts `tasks()` uses as capacity — called by
        `attach_running_task_registry()` once `AppConfigFile`'s `*_queue_workers` fields
        are known, so the "queued" badge matches the executor sizes
        `scheduling.scheduler.build_scheduler()` was actually given rather than the
        `QUEUE_WORKERS` defaults."""
        with self._lock:
            self._queue_workers = queue_workers

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

    def report_progress(
        self,
        job_id: str,
        *,
        phase: str,
        current: int,
        total: int,
        language: str,
        provider: str | None = None,
    ) -> None:
        """Attach a progress checkpoint to every currently-running task matching
        `job_id`. A no-op if `job_id` isn't running right now (e.g. it just finished) —
        same posture as `finish()` on an unknown key, since a stray/late report is
        harmless to drop.
        """
        with self._lock:
            for key, task in list(self._tasks.items()):
                if key[0] != job_id:
                    continue
                self._tasks[key] = replace(
                    task,
                    phase=phase,
                    current_step=current,
                    total_steps=total,
                    language=language,
                    provider=provider,
                )

    def tasks(self) -> list[RunningTask]:
        """Every submitted-but-not-finished task, `queued` flagged for the ones that
        haven't actually started executing yet.

        `_tasks` preserves submission order (dict insertion order), and so does each
        queue's own `ThreadPoolExecutor` — one shared FIFO work queue per executor,
        regardless of how many jobs got submitted to it at once. So the first
        `QUEUE_WORKERS[queue]` not-yet-finished tasks *for that queue*, in submission
        order, are the ones a worker thread is genuinely running right now; anything past
        that is still waiting in line behind them, no matter how long ago it was submitted.
        """
        with self._lock:
            in_flight: dict[str, int] = {}
            result = []
            for task in self._tasks.values():
                ahead = in_flight.get(task.queue, 0)
                in_flight[task.queue] = ahead + 1
                # `task.queue` is always a `JobQueue.value` set at `add_job` time
                # (`job.executor`) — round-trip it back to the enum `QUEUE_WORKERS` is
                # keyed by instead of relying on `StrEnum`'s str-equality for the lookup.
                capacity = self._queue_workers.get(JobQueue(task.queue), 1)
                result.append(task if ahead < capacity else replace(task, queued=True))
            return result

    def clear(self) -> None:
        with self._lock:
            self._tasks.clear()
            self._job_meta.clear()
            self._queue_workers = QUEUE_WORKERS


_registry = RunningTaskRegistry()


def attach_running_task_registry(
    scheduler: BackgroundScheduler, queue_workers: dict[JobQueue, int] | None = None
) -> None:
    """Wire the shared registry onto `scheduler`'s event stream.

    Call once per scheduler instance, alongside where its periodic jobs are registered
    (`legendarr_backend/bootstrap.py`).

    `queue_workers` — when given, the same map `scheduling.scheduler.build_scheduler()`
    sized its executors with (`legendarr_backend.bootstrap.build_scheduler()` builds one
    from `AppConfigFile`'s `*_queue_workers` fields and passes it to both) — is applied
    via `configure()` so `tasks()`'s "queued" capacity matches those executors instead of
    the `QUEUE_WORKERS` defaults.
    """
    if queue_workers is not None:
        _registry.configure(queue_workers)
    scheduler.add_listener(
        lambda event: _registry.remember(event, scheduler), EVENT_JOB_ADDED | EVENT_JOB_MODIFIED
    )
    scheduler.add_listener(lambda event: _registry.submit(event, scheduler), EVENT_JOB_SUBMITTED)
    scheduler.add_listener(
        _registry.finish, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR | EVENT_JOB_MISSED
    )


def get_running_tasks() -> list[RunningTask]:
    """Return the tasks currently handed to an executor — each flagged `queued=True`
    unless a worker thread is genuinely running it right now, see `RunningTaskRegistry.tasks()`.
    """
    return _registry.tasks()


def report_progress(
    job_id: str,
    *,
    phase: str,
    current: int,
    total: int,
    language: str,
    provider: str | None = None,
) -> None:
    """Report a progress checkpoint for the running task `job_id`, for the topbar/System
    → Tasks/Dashboard "live progress" UI (ROADMAP 0.20.0). Called by
    `subtitle_translation.jobs`/`subtitle_acquisition.jobs` — the only slices that know
    both a job's `job_id` and its domain-specific progress.
    """
    _registry.report_progress(
        job_id, phase=phase, current=current, total=total, language=language, provider=provider
    )


def reset_running_tasks() -> None:
    """Clear the in-memory running-task state. For test isolation only."""
    _registry.clear()
