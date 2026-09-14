import time
from datetime import UTC, datetime

from apscheduler.events import EVENT_JOB_SUBMITTED, JobSubmissionEvent
from legendarr_backend.database.engine import get_engine, get_session
from legendarr_backend.maintenance.reap_stuck_tasks import reap_stuck_tasks
from legendarr_backend.scheduling import running_tasks as running_tasks_module
from legendarr_backend.scheduling.job_timeout import configure_job_timeouts
from legendarr_backend.scheduling.queues import JobQueue
from legendarr_backend.scheduling.running_tasks import get_running_tasks, is_task_active
from legendarr_backend.scheduling.scheduler import build_scheduler, register_job
from legendarr_backend.system.models import JobRun
from sqlmodel import SQLModel, select


def _noop() -> None:
    pass


def _submit(scheduler, job_id: str, queue: JobQueue) -> None:
    register_job(
        scheduler,
        _noop,
        queue=queue,
        job_id=job_id,
        trigger="interval",
        minutes=1,
        retry_attempts=1,
        retry_delay_seconds=0,
        max_instances=1,
        coalesce=False,
    )
    running_tasks_module._registry.submit(
        JobSubmissionEvent(EVENT_JOB_SUBMITTED, job_id, "default", [datetime.now(UTC)]), scheduler
    )


def _job_runs() -> list[JobRun]:
    with get_session() as session:
        return list(session.exec(select(JobRun)))


def test_a_task_past_its_budget_is_dropped_and_recorded_as_abandoned(
    isolated_database, isolated_running_tasks, isolated_job_timeouts
):
    """The limbo the sweep exists to end: while the registry entry lives, `is_task_active`
    keeps every `enqueue_*` skipping that media file, so nothing ever retries it."""
    SQLModel.metadata.create_all(get_engine())
    configure_job_timeouts({JobQueue.SCAN_BULK: 0.001})
    scheduler = build_scheduler()
    _submit(scheduler, "subtitle_scan:1", JobQueue.SCAN_BULK)
    assert is_task_active("subtitle_scan:1") is True
    # Elapsed execution time only starts counting once the registry has seen the task off
    # the queue — see `RunningTask.running_since`.
    get_running_tasks()
    time.sleep(0.01)

    assert reap_stuck_tasks(grace_seconds=0) == 1

    assert is_task_active("subtitle_scan:1") is False
    runs = _job_runs()
    assert [(run.job_id, run.status, run.queue) for run in runs] == [
        ("subtitle_scan:1", "abandoned", JobQueue.SCAN_BULK.value)
    ]
    assert runs[0].error_message is not None


def test_a_task_still_within_its_budget_is_left_alone(
    isolated_database, isolated_running_tasks, isolated_job_timeouts
):
    SQLModel.metadata.create_all(get_engine())
    scheduler = build_scheduler()
    _submit(scheduler, "subtitle_scan:1", JobQueue.SCAN_BULK)

    assert reap_stuck_tasks(grace_seconds=0) == 0

    assert is_task_active("subtitle_scan:1") is True
    assert _job_runs() == []
