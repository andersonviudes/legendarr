from collections.abc import Callable
from typing import Any

from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.schedulers.background import BackgroundScheduler

from legendarr_backend.scheduling.queues import QUEUE_WORKERS, JobQueue
from legendarr_backend.scheduling.retry import with_retry

# Every periodic job is left to APScheduler's default first-fire (registration time +
# interval), so jobs registered back-to-back at boot with the same interval (several are
# 60 minutes, see each slice's `jobs.py`) would otherwise wake up in the exact same
# instant forever. A small random jitter desyncs them without changing their nominal
# schedule, so they don't all queue up behind each other on a shared executor.
JOB_JITTER_SECONDS = 60


def build_scheduler() -> BackgroundScheduler:
    """Construct a scheduler with one executor per named queue.

    Job-agnostic: no job is registered here. Slices register their own jobs onto this
    scheduler via `register_job`.
    """
    executors = {
        queue.value: ThreadPoolExecutor(max_workers=workers)
        for queue, workers in QUEUE_WORKERS.items()
    }
    # Explicit UTC — APScheduler otherwise defaults to the host's local tz (via
    # `tzlocal`), which would make `next_run_time`/`scheduled_run_time` ambiguous
    # wherever they're displayed. Every job registered here is `trigger="interval"`, so
    # this doesn't change *when* anything runs, only the tz label on the result.
    return BackgroundScheduler(executors=executors, timezone="UTC")


def register_job(
    scheduler: BackgroundScheduler,
    func: Callable[[], None],
    *,
    queue: JobQueue,
    job_id: str,
    trigger: str,
    retry_attempts: int,
    retry_delay_seconds: float,
    max_instances: int,
    coalesce: bool,
    **trigger_args: Any,
) -> None:
    """Register `func` as a job, applying this project's shared scheduling conventions.

    Wraps `func` with a retry policy, and registers it under `job_id` on the given named
    queue with a concurrency-dedup policy (`max_instances`/`coalesce`) — so every job
    follows the same shape instead of each caller configuring `add_job` from scratch.
    Re-registering the same `job_id` replaces the existing job rather than duplicating it.

    Defaults to a `JOB_JITTER_SECONDS` jitter unless the caller passes its own `jitter`
    trigger arg — both `IntervalTrigger` and `CronTrigger` support it natively.
    """
    trigger_args.setdefault("jitter", JOB_JITTER_SECONDS)
    scheduler.add_job(
        with_retry(func, max_attempts=retry_attempts, delay_seconds=retry_delay_seconds),
        trigger,
        id=job_id,
        name=job_id,
        executor=queue.value,
        max_instances=max_instances,
        coalesce=coalesce,
        replace_existing=True,
        **trigger_args,
    )
