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
    report_progress,
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


def _register_and_submit(
    scheduler: BackgroundScheduler, registry: RunningTaskRegistry, job_id: str, queue: JobQueue
) -> datetime:
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
    registry.remember(_added_event(job_id), scheduler)
    run_time = datetime.now(UTC)
    registry.submit(
        JobSubmissionEvent(EVENT_JOB_SUBMITTED, job_id, "default", [run_time]), scheduler
    )
    return run_time


def test_tasks_flags_extra_submissions_as_queued_when_the_queue_has_one_worker():
    """The regression this exists to prevent: `scan_bulk` has exactly one worker
    (`scheduling/queues.py`), and the bulk fan-out submits one job per media file in a
    tight loop (`subtitle_discovery/jobs.py`'s `enqueue_full_subtitle_scan`) — only the
    first should ever show as genuinely running.
    """
    scheduler = build_scheduler()
    registry = RunningTaskRegistry()
    for job_id in ("scan_1", "scan_2", "scan_3"):
        _register_and_submit(scheduler, registry, job_id, JobQueue.SCAN_BULK)

    assert {task.job_id: task.queued for task in registry.tasks()} == {
        "scan_1": False,
        "scan_2": True,
        "scan_3": True,
    }


def test_tasks_uses_each_queues_own_worker_count_as_capacity():
    """`translate` has two workers (`scheduling/queues.py`) — the first two submissions
    are genuinely running at once, only the third is queued."""
    scheduler = build_scheduler()
    registry = RunningTaskRegistry()
    for job_id in ("t1", "t2", "t3"):
        _register_and_submit(scheduler, registry, job_id, JobQueue.TRANSLATE)

    assert {task.job_id: task.queued for task in registry.tasks()} == {
        "t1": False,
        "t2": False,
        "t3": True,
    }


def test_tasks_promotes_the_next_queued_job_once_the_running_one_finishes():
    scheduler = build_scheduler()
    registry = RunningTaskRegistry()
    first_run = _register_and_submit(scheduler, registry, "scan_1", JobQueue.SCAN_BULK)
    _register_and_submit(scheduler, registry, "scan_2", JobQueue.SCAN_BULK)
    assert {task.job_id: task.queued for task in registry.tasks()} == {
        "scan_1": False,
        "scan_2": True,
    }

    registry.finish(JobExecutionEvent(EVENT_JOB_EXECUTED, "scan_1", "default", first_run))

    assert {task.job_id: task.queued for task in registry.tasks()} == {"scan_2": False}


def test_report_progress_updates_the_matching_task():
    scheduler = _scheduler_with_job()
    registry = RunningTaskRegistry()
    run_time = datetime.now(UTC)
    registry.remember(_added_event("test_job"), scheduler)
    registry.submit(
        JobSubmissionEvent(EVENT_JOB_SUBMITTED, "test_job", "default", [run_time]), scheduler
    )

    registry.report_progress("test_job", phase="translating", current=1, total=3, language="pt-BR")

    task = registry.tasks()[0]
    assert task.phase == "translating"
    assert task.current_step == 1
    assert task.total_steps == 3
    assert task.language == "pt-BR"
    assert task.provider is None


def test_report_progress_carries_a_provider_when_given():
    scheduler = _scheduler_with_job()
    registry = RunningTaskRegistry()
    run_time = datetime.now(UTC)
    registry.remember(_added_event("test_job"), scheduler)
    registry.submit(
        JobSubmissionEvent(EVENT_JOB_SUBMITTED, "test_job", "default", [run_time]), scheduler
    )

    registry.report_progress(
        "test_job", phase="searching", current=1, total=2, language="en", provider="opensubtitles"
    )

    assert registry.tasks()[0].provider == "opensubtitles"


def test_report_progress_for_a_job_not_running_is_a_noop():
    registry = RunningTaskRegistry()

    registry.report_progress("missing_job", phase="translating", current=1, total=1, language="en")

    assert registry.tasks() == []


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


def test_module_level_report_progress_updates_the_shared_registry():
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
        scheduler.add_job(slow_job, "date", id="e2e_progress", executor=JobQueue.SYNC.value)
        assert started.wait(timeout=5)
        for _ in range(50):
            if get_running_tasks():
                break
            time.sleep(0.02)

        report_progress("e2e_progress", phase="translating", current=1, total=1, language="pt-BR")

        tasks = get_running_tasks()
        assert len(tasks) == 1
        assert tasks[0].phase == "translating"
    finally:
        finish.set()
        scheduler.shutdown(wait=False)
        reset_running_tasks()


def _added_event(job_id: str) -> JobEvent:
    return JobEvent(EVENT_JOB_ADDED, job_id, "default")
