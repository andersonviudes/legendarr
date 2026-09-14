import logging
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

from legendarr_backend.scheduling.job_timeout import job_timeout_seconds
from legendarr_backend.scheduling.queues import QUEUE_WORKERS, JobQueue

logger = logging.getLogger(__name__)

# Fallback for how long a genuinely-running (not queued) task may go without finishing
# before `RunningTaskRegistry.tasks()` flags it as stalled. Normally the threshold is the
# task's own queue budget (`scheduling/job_timeout.job_timeout_seconds`): a run that
# outlives its budget and is *still* here means the budget didn't take, which is exactly
# what's worth flagging. This constant only covers a queue whose budget was turned off
# (set to `0`), where there's no per-queue number to lean on — set well above the slowest
# job that's still working normally (`Settings.speech_to_text_timeout_seconds` alone
# allows 1800s for a single file) so "slow" is never reported as "stuck".
STALLED_TASK_THRESHOLD_SECONDS = 7200.0

# How far past its stall threshold a still-running task goes before the periodic sweep
# (`maintenance/reap_stuck_tasks.py`) drops it from this registry altogether. Generous on
# purpose: the normal path is the execution budget failing the run and `finish()` clearing
# the entry through the resulting `EVENT_JOB_ERROR`, so anything this sweep catches is a
# task whose budget never fired at all. The grace period is what keeps a run that was
# merely slow to emit its completion event from being declared abandoned.
STUCK_TASK_EVICTION_GRACE_SECONDS = 300.0


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
    # When a worker thread was first *observed* to be running this task, as opposed to
    # `started_at`, which is really "submitted at". Set by `_annotated()` the first time it
    # sees the task off the queue; `None` while it's still waiting its turn. This — not
    # `started_at` — is the only sound elapsed-time anchor: on a `_bulk` queue a fan-out
    # submits thousands of jobs at once, so a job that waits four hours in the FIFO and
    # then runs normally has a four-hour-old `started_at` the instant it starts.
    running_since: datetime | None = None
    # Live-progress fields (ROADMAP 0.20.0's "Live progress") — all unset until the
    # running job's own code reports a checkpoint via `report_progress()`. `phase` is a
    # domain-defined string ("translating", "searching", ...) the caller picks; this
    # module has no opinion on what phases exist.
    phase: str | None = None
    current_step: int | None = None
    total_steps: int | None = None
    language: str | None = None
    provider: str | None = None
    # Set by `tasks()`, not by `submit()`, same as `queued` — a task that's been
    # executing longer than its queue's execution budget (see `_stall_threshold_seconds`),
    # measured from `running_since`. Never set on a queued task, which hasn't started.
    stalled: bool = False


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
        # `tasks()`'s one-warning-per-stalled-task guard — keyed like `_tasks` and
        # pruned alongside it, so a long-lived process doesn't accumulate keys for
        # tasks that finished ages ago.
        self._stall_warned: set[tuple[str, datetime]] = set()
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
            self._stall_warned.discard((event.job_id, event.scheduled_run_time))

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

    def _annotated(self) -> list[tuple[tuple[str, datetime], RunningTask]]:
        """Every tracked task paired with its key, `queued`/`stalled` filled in. The
        caller holds the lock.

        `_tasks` preserves submission order (dict insertion order), and so does each
        queue's own `ThreadPoolExecutor` — one shared FIFO work queue per executor,
        regardless of how many jobs got submitted to it at once. So the first
        `QUEUE_WORKERS[queue]` not-yet-finished tasks *for that queue*, in submission
        order, are the ones a worker thread is genuinely running right now; anything past
        that is still waiting in line behind them, no matter how long ago it was submitted.

        Stamps `running_since` on a task the first time it's seen off the queue, which is
        why this writes back to `_tasks` rather than only deriving. Nothing else observes
        the queued-to-running transition: APScheduler emits an event on submission and on
        completion, never on start. The stamp is therefore "first observed running", up to
        one poll interval late (3s while any UI is open, 15 minutes from the sweep alone) —
        always late, never early, so it can only ever delay a stall verdict.
        """
        in_flight: dict[str, int] = {}
        annotated: list[tuple[tuple[str, datetime], RunningTask]] = []
        now = datetime.now()
        for key, task in self._tasks.items():
            ahead = in_flight.get(task.queue, 0)
            in_flight[task.queue] = ahead + 1
            # `task.queue` is always a `JobQueue.value` set at `add_job` time
            # (`job.executor`) — round-trip it back to the enum `QUEUE_WORKERS` is
            # keyed by instead of relying on `StrEnum`'s str-equality for the lookup.
            capacity = self._queue_workers.get(JobQueue(task.queue), 1)
            queued = ahead >= capacity
            if not queued and task.running_since is None:
                task = replace(task, running_since=now)
                self._tasks[key] = task
            stalled = not queued and _has_stalled(task, now=now)
            annotated.append((key, replace(task, queued=queued, stalled=stalled)))
        return annotated

    def tasks(self) -> list[RunningTask]:
        """Every submitted-but-not-finished task, `queued` flagged for the ones that
        haven't actually started executing yet and `stalled` for the ones that have
        been executing too long to still be working.

        See `_annotated` for how the two are told apart. A newly stalled task is also
        warned about, once each — a job that never returns never fires the
        `JobExecutionEvent` `finish()` waits for, so nothing else would ever mention it.
        """
        newly_stalled: list[RunningTask] = []
        with self._lock:
            annotated = self._annotated()
            result = [task for _, task in annotated]
            for key, task in annotated:
                if task.stalled and key not in self._stall_warned:
                    self._stall_warned.add(key)
                    newly_stalled.append(task)
        for task in newly_stalled:
            logger.warning(
                "task %r on queue %r has been running since %s without finishing — its "
                "worker slot stays taken until the process restarts",
                task.job_id,
                task.queue,
                (task.running_since or task.started_at).isoformat(timespec="seconds"),
            )
        return result

    def is_active(self, job_id: str) -> bool:
        """Whether `job_id` is already dispatched to an executor — either genuinely
        running or still waiting its turn behind other same-queue work (`tasks()`'s
        `queued`). Doesn't distinguish the two: either way, a caller about to re-enqueue
        this `job_id` would just be piling up a duplicate rather than making it start any
        sooner, and (unlike `scheduler.get_job`) this catches a job that's already left
        the jobstore for an executor, which is exactly the case a plain
        `replace_existing` dedupe misses.
        """
        with self._lock:
            return any(key[0] == job_id for key in self._tasks)

    def evict(self, job_id: str) -> list[RunningTask]:
        """Drop every *running* entry for `job_id` and return what was dropped.

        For a job whose completion event is never coming. Dropping the entry is what makes
        `is_active()` report it as finished again — so the item it was working on gets
        picked up by the next fan-out instead of being skipped forever — and what takes the
        stale row off the Tasks page.

        Entries still queued behind other work are left alone, same as `evict_stuck`: they
        haven't started, so there is nothing stuck about them, and recording one as an
        abandoned run would be a plain lie. A job with several submissions in flight
        (`max_instances > 1`, or a `coalesce=False` job that missed ticks) therefore keeps
        its queued ones.

        What it does *not* do is stop the job. A thread blocked in a syscall can't be
        interrupted from Python, so if the execution budget didn't manage to release the
        worker slot, neither does this: the queue's real capacity stays reduced until the
        process restarts — and on a queue whose budget is off, APScheduler's own
        `max_instances` accounting stays pinned too (it's only decremented when a run
        returns), so a re-enqueue is dropped as `EVENT_JOB_MAX_INSTANCES` until restart.
        This is bookkeeping, not cancellation.
        """
        with self._lock:
            evicted: list[RunningTask] = []
            for key, task in self._annotated():
                if key[0] != job_id or task.queued:
                    continue
                self._tasks.pop(key, None)
                self._stall_warned.discard(key)
                evicted.append(task)
            return evicted

    def evict_stuck(
        self, grace_seconds: float = STUCK_TASK_EVICTION_GRACE_SECONDS
    ) -> list[RunningTask]:
        """Drop every genuinely-running task that's `grace_seconds` past its stall
        threshold and return what was dropped — the sweep behind
        `maintenance/reap_stuck_tasks.py`.

        Queued tasks are never candidates — they haven't started. Neither is a task on a
        queue whose budget is off: setting `<queue>_job_timeout_seconds = 0` is documented
        as removing that queue's time limit, and evicting on the fallback threshold anyway
        would kill exactly the long-but-healthy runs the escape hatch exists for. Those
        tasks still get the `stalled` badge, which is visibility only.

        Same bookkeeping-not-cancellation caveat as `evict`.
        """
        now = datetime.now()
        with self._lock:
            evicted: list[RunningTask] = []
            for key, task in self._annotated():
                if not task.stalled:
                    continue
                budget = job_timeout_seconds(JobQueue(task.queue))
                if budget <= 0:
                    continue
                anchor = task.running_since or task.started_at
                if (now - anchor).total_seconds() < budget + grace_seconds:
                    continue
                self._tasks.pop(key, None)
                self._stall_warned.discard(key)
                evicted.append(task)
            return evicted

    def clear(self) -> None:
        with self._lock:
            self._tasks.clear()
            self._job_meta.clear()
            self._stall_warned.clear()
            self._queue_workers = QUEUE_WORKERS


def _stall_threshold_seconds(queue: str) -> float:
    """How long a running task on `queue` may go without finishing before it counts as
    stalled: that queue's own execution budget, or `STALLED_TASK_THRESHOLD_SECONDS` when
    the budget is turned off."""
    budget = job_timeout_seconds(JobQueue(queue))
    return budget if budget > 0 else STALLED_TASK_THRESHOLD_SECONDS


def _has_stalled(task: RunningTask, *, now: datetime) -> bool:
    """Whether `task` has been *executing* longer than its queue allows. Measured from
    `running_since`, never from `started_at` — see that field's comment."""
    if task.running_since is None:
        return False
    return (now - task.running_since).total_seconds() >= _stall_threshold_seconds(task.queue)


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


def is_task_active(job_id: str) -> bool:
    """Whether `job_id` is already dispatched to an executor. Every ad-hoc per-item
    `enqueue_*` job (`subtitle_acquisition.jobs`, `subtitle_translation.jobs`, ...) checks
    this before scheduling, to skip a redundant re-enqueue instead of silently duplicating
    it once the original job leaves the jobstore for an executor — see
    `RunningTaskRegistry.is_active`.
    """
    return _registry.is_active(job_id)


def evict_task(job_id: str) -> list[RunningTask]:
    """Drop every running registry entry for `job_id`, returning what was dropped — the manual
    "dismiss" action on the System → Tasks page (`system/dismiss_running_task.py`). See
    `RunningTaskRegistry.evict` for what this does and does not accomplish.
    """
    return _registry.evict(job_id)


def evict_stuck_tasks(
    grace_seconds: float = STUCK_TASK_EVICTION_GRACE_SECONDS,
) -> list[RunningTask]:
    """Drop every running task well past its stall threshold, returning what was dropped —
    the periodic sweep in `maintenance/reap_stuck_tasks.py`. See
    `RunningTaskRegistry.evict_stuck`.
    """
    return _registry.evict_stuck(grace_seconds)


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
