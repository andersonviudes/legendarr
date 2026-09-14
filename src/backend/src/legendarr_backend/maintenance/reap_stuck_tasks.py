import logging

from legendarr_backend.scheduling.running_tasks import (
    STUCK_TASK_EVICTION_GRACE_SECONDS,
    evict_stuck_tasks,
)
from legendarr_backend.system.job_history import record_abandoned_runs

logger = logging.getLogger(__name__)

_REASON = "no completion event arrived within this queue's execution budget"


def reap_stuck_tasks(grace_seconds: float = STUCK_TASK_EVICTION_GRACE_SECONDS) -> int:
    """Drop every running task well past its queue's execution budget from the
    running-task registry, record each as an abandoned `JobRun`, and return how many.

    The safety net behind the execution budget, not a replacement for it. Normally a run
    that overruns raises out of `scheduling/job_timeout.with_timeout`, APScheduler fires
    `EVENT_JOB_ERROR`, and `RunningTaskRegistry.finish()` clears the entry — nothing
    reaches this sweep. What reaches it is a run whose budget didn't take (the ceiling in
    `MAX_ABANDONED_JOB_THREADS` was hit, so the wrapper went back to waiting; or a
    listener failed), and whose entry would otherwise live until the process restarts.

    That stale entry is not cosmetic: `running_tasks.is_task_active` treats it as still in
    flight, so every `enqueue_*` skips that media file for good. Dropping it is what lets
    the next fan-out pick the item up again.

    It does not free the queue's worker slot — see `RunningTaskRegistry.evict`. If the
    budget didn't manage to hand the executor thread back, nothing short of a restart will.
    """
    evicted = evict_stuck_tasks(grace_seconds)
    for task in evicted:
        logger.warning(
            "dropped task %r on queue %r, running since %s, from the running-task "
            "registry — it never reported an outcome",
            task.job_id,
            task.queue,
            (task.running_since or task.started_at).isoformat(timespec="seconds"),
        )
    return record_abandoned_runs(evicted, reason=_REASON)
