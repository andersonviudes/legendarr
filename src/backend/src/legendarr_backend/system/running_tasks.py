from legendarr_backend.scheduling.running_tasks import get_running_tasks
from legendarr_backend.system.schemas import RunningTaskRead


def list_running_tasks() -> list[RunningTaskRead]:
    """Return the tasks currently executing, most recently started first."""
    tasks = sorted(get_running_tasks(), key=lambda task: task.started_at, reverse=True)
    return [
        RunningTaskRead(
            job_id=task.job_id,
            name=task.name,
            queue=task.queue,
            started_at=task.started_at,
            queued=task.queued,
            phase=task.phase,
            current_step=task.current_step,
            total_steps=task.total_steps,
            language=task.language,
            provider=task.provider,
        )
        for task in tasks
    ]
