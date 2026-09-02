from sqlmodel import Session

from legendarr_backend.scheduling.running_tasks import get_running_tasks
from legendarr_backend.system.resolve_job_media_title import resolve_job_media_titles
from legendarr_backend.system.schemas import RunningTaskRead


def list_running_tasks(session: Session) -> list[RunningTaskRead]:
    """Return the tasks currently executing first, then the rest in the order they'll
    run. `get_running_tasks()` already returns tasks in submission/FIFO order (see
    `RunningTaskRegistry.tasks()`'s docstring), so a stable sort on `queued` alone
    bubbles the in-flight tasks to the front without disturbing that order otherwise."""
    tasks = sorted(get_running_tasks(), key=lambda task: task.queued)
    display_names = resolve_job_media_titles(session, (task.job_id for task in tasks))
    return [
        RunningTaskRead(
            job_id=task.job_id,
            name=display_names.get(task.job_id, task.name),
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
