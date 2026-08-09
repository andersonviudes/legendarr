from collections.abc import Callable

from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.schedulers.background import BackgroundScheduler

from legendarr_backend.scheduling.queues import QUEUE_WORKERS, JobQueue
from legendarr_backend.scheduling.retry import with_retry


def build_scheduler() -> BackgroundScheduler:
    """Construct a scheduler with one executor per named queue.

    Job-agnostic: no job is registered here. Slices register their own jobs onto this
    scheduler via `register_job`.
    """
    executors = {
        queue.value: ThreadPoolExecutor(max_workers=workers)
        for queue, workers in QUEUE_WORKERS.items()
    }
    return BackgroundScheduler(executors=executors)


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
    **trigger_args: object,
) -> None:
    """Register `func` as a job, applying this project's shared scheduling conventions.

    Wraps `func` with a retry policy, and registers it under `job_id` on the given named
    queue with a concurrency-dedup policy (`max_instances`/`coalesce`) — so every job
    follows the same shape instead of each caller configuring `add_job` from scratch.
    Re-registering the same `job_id` replaces the existing job rather than duplicating it.
    """
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
