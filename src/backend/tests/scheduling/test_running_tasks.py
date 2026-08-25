from datetime import UTC, datetime, timedelta

from apscheduler.events import (
    EVENT_JOB_EXECUTED,
    EVENT_JOB_SUBMITTED,
    JobExecutionEvent,
    JobSubmissionEvent,
)
from apscheduler.schedulers.background import BackgroundScheduler
from legendarr_backend.scheduling.queues import JobQueue
from legendarr_backend.scheduling.running_tasks import RunningTaskRegistry
from legendarr_backend.scheduling.scheduler import build_scheduler, register_job


def _noop() -> None:
    pass


def _scheduler_with_job(job_id: str = "test_job") -> BackgroundScheduler:
    scheduler = build_scheduler()
    register_job(
        scheduler,
        _noop,
        queue=JobQueue.SYNC,
        job_id=job_id,
        trigger="interval",
        minutes=1,
        retry_attempts=1,
        retry_delay_seconds=0,
        max_instances=2,
        coalesce=False,
    )
    return scheduler


def test_submit_adds_a_running_task():
    scheduler = _scheduler_with_job()
    registry = RunningTaskRegistry()
    run_time = datetime.now(UTC)

    registry.submit(
        JobSubmissionEvent(EVENT_JOB_SUBMITTED, "test_job", "default", [run_time]), scheduler
    )

    tasks = registry.tasks()
    assert len(tasks) == 1
    assert tasks[0].job_id == "test_job"
    assert tasks[0].name == "test_job"
    assert tasks[0].queue == JobQueue.SYNC.value


def test_submit_for_a_job_no_longer_in_the_jobstore_is_a_noop():
    scheduler = build_scheduler()
    registry = RunningTaskRegistry()

    registry.submit(
        JobSubmissionEvent(EVENT_JOB_SUBMITTED, "missing_job", "default", [datetime.now(UTC)]),
        scheduler,
    )

    assert registry.tasks() == []


def test_finish_removes_the_matching_task():
    scheduler = _scheduler_with_job()
    registry = RunningTaskRegistry()
    run_time = datetime.now(UTC)
    registry.submit(
        JobSubmissionEvent(EVENT_JOB_SUBMITTED, "test_job", "default", [run_time]), scheduler
    )

    registry.finish(JobExecutionEvent(EVENT_JOB_EXECUTED, "test_job", "default", run_time))

    assert registry.tasks() == []


def test_finish_for_an_unknown_run_time_is_a_noop():
    registry = RunningTaskRegistry()

    registry.finish(
        JobExecutionEvent(EVENT_JOB_EXECUTED, "unknown_job", "default", datetime.now(UTC))
    )

    assert registry.tasks() == []


def test_two_concurrent_instances_of_the_same_job_dont_collide():
    scheduler = _scheduler_with_job()
    registry = RunningTaskRegistry()
    first_run = datetime.now(UTC)
    second_run = first_run + timedelta(seconds=1)
    registry.submit(
        JobSubmissionEvent(EVENT_JOB_SUBMITTED, "test_job", "default", [first_run]), scheduler
    )
    registry.submit(
        JobSubmissionEvent(EVENT_JOB_SUBMITTED, "test_job", "default", [second_run]), scheduler
    )

    assert len(registry.tasks()) == 2

    registry.finish(JobExecutionEvent(EVENT_JOB_EXECUTED, "test_job", "default", first_run))

    assert len(registry.tasks()) == 1
