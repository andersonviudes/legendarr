import logging

from legendarr_backend.scheduling.running_tasks import evict_task
from legendarr_backend.system.job_history import record_abandoned_runs

logger = logging.getLogger(__name__)

_REASON = "dismissed from the running-task registry by a user"


def dismiss_running_task(job_id: str) -> int:
    """Drop every running entry for `job_id`, record each as an abandoned `JobRun`, and
    return how many were dropped (`0` if it wasn't running).

    The on-demand counterpart to `maintenance/reap_stuck_tasks.py`'s periodic sweep, for a
    task the user can see is stuck and doesn't want to wait out. It clears the bookkeeping
    — the stale row on the Tasks page, and the `running_tasks.is_task_active` entry that
    would otherwise make every `enqueue_*` skip that media file forever — so the next
    fan-out picks the item up again.

    It does not cancel anything. A thread blocked in a syscall can't be interrupted from
    Python, so whatever the job is stuck on keeps its worker slot until the process
    restarts; the UI copy says as much, and it must keep saying so. On a queue whose budget
    is turned off, APScheduler's own `max_instances` accounting stays pinned too, so the
    re-enqueue this unblocks is dropped as `EVENT_JOB_MAX_INSTANCES` until restart —
    dismissing there tidies the UI without actually recovering the item.
    """
    evicted = evict_task(job_id)
    for task in evicted:
        logger.warning(
            "task %r on queue %r, running since %s, was dismissed from the running-task "
            "registry by a user",
            task.job_id,
            task.queue,
            (task.running_since or task.started_at).isoformat(timespec="seconds"),
        )
    return record_abandoned_runs(evicted, reason=_REASON)
