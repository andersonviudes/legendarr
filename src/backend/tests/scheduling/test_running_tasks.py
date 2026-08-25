import threading
import time
from datetime import UTC, datetime, timedelta

from apscheduler.events import (
    EVENT_JOB_ADDED,
    EVENT_JOB_EXECUTED,
    EVENT_JOB_SUBMITTED,
    JobEvent,
    JobExecutionEvent,
    JobSubmissionEvent,
)
from apscheduler.schedulers.background import BackgroundScheduler
from legendarr_backend.scheduling.queues import JobQueue
from legendarr_backend.scheduling.running_tasks import (
    RunningTaskRegistry,
    attach_running_task_registry,
    get_running_tasks,
    reset_running_tasks,
)
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
    registry.remember(_added_event("test_job"), scheduler)

    registry.submit(
        JobSubmissionEvent(EVENT_JOB_SUBMITTED, "test_job", "default", [run_time]), scheduler
    )

    tasks = registry.tasks()
    assert len(tasks) == 1
    assert tasks[0].job_id == "test_job"
    assert tasks[0].name == "test_job"
    assert tasks[0].queue == JobQueue.SYNC.value


def test_submit_for_a_job_never_remembered_is_a_noop():
    scheduler = build_scheduler()
    registry = RunningTaskRegistry()

    registry.submit(
        JobSubmissionEvent(EVENT_JOB_SUBMITTED, "missing_job", "default", [datetime.now(UTC)]),
        scheduler,
    )

    assert registry.tasks() == []


def test_remember_for_a_job_no_longer_in_the_jobstore_is_a_noop():
    scheduler = build_scheduler()
    registry = RunningTaskRegistry()

    registry.remember(_added_event("missing_job"), scheduler)
    registry.submit(
        JobSubmissionEvent(EVENT_JOB_SUBMITTED, "missing_job", "default", [datetime.now(UTC)]),
        scheduler,
    )

    assert registry.tasks() == []


def test_submit_for_a_one_off_job_already_removed_from_the_jobstore_still_shows_up():
    """The regression this module exists to prevent: `"date"`-triggered one-off jobs (every
    manual "Sync Now"/"Scan Disk" trigger) are gone from the jobstore by the time
    `EVENT_JOB_SUBMITTED` fires, so `submit()` can't rely on `scheduler.get_job()` — it must
    use what `remember()` cached off `EVENT_JOB_ADDED` while the job still existed.
    """
    scheduler = _scheduler_with_job("one_off_job")
    registry = RunningTaskRegistry()
    registry.remember(_added_event("one_off_job"), scheduler)
    scheduler.remove_job("one_off_job")  # gone from the jobstore, same as after a "date" run

    registry.submit(
        JobSubmissionEvent(EVENT_JOB_SUBMITTED, "one_off_job", "default", [datetime.now(UTC)]),
        scheduler,
    )

    tasks = registry.tasks()
    assert len(tasks) == 1
    assert tasks[0].job_id == "one_off_job"


def test_finish_removes_the_matching_task():
    scheduler = _scheduler_with_job()
    registry = RunningTaskRegistry()
    run_time = datetime.now(UTC)
    registry.remember(_added_event("test_job"), scheduler)
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
    registry.remember(_added_event("test_job"), scheduler)
    registry.submit(
        JobSubmissionEvent(EVENT_JOB_SUBMITTED, "test_job", "default", [first_run]), scheduler
    )
    registry.submit(
        JobSubmissionEvent(EVENT_JOB_SUBMITTED, "test_job", "default", [second_run]), scheduler
    )

    assert len(registry.tasks()) == 2

    registry.finish(JobExecutionEvent(EVENT_JOB_EXECUTED, "test_job", "default", first_run))

    assert len(registry.tasks()) == 1


def test_end_to_end_a_real_one_off_job_run_through_a_real_scheduler_shows_up_while_running():
    """No synthetic events: drives an actual `BackgroundScheduler` through `add_job` for a
    one-off `"date"` trigger, the same shape as every manual "Sync Now"/"Scan Disk" trigger.
    """
    reset_running_tasks()
    scheduler = build_scheduler()
    attach_running_task_registry(scheduler)
    scheduler.start()
    started = threading.Event()
    finish = threading.Event()

    def slow_job() -> None:
        started.set()
        finish.wait(timeout=5)

    try:
        scheduler.add_job(slow_job, "date", id="e2e_one_off", executor=JobQueue.SYNC.value)
        assert started.wait(timeout=5)
        # Give the SUBMITTED listener a moment to run on the scheduler's own thread.
        for _ in range(50):
            if get_running_tasks():
                break
            time.sleep(0.02)
        tasks = get_running_tasks()
        assert len(tasks) == 1
        assert tasks[0].job_id == "e2e_one_off"
    finally:
        finish.set()
        scheduler.shutdown(wait=False)
        reset_running_tasks()


def _added_event(job_id: str) -> JobEvent:
    return JobEvent(EVENT_JOB_ADDED, job_id, "default")
