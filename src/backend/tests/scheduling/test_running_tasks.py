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
from legendarr_backend.scheduling import running_tasks as running_tasks_module
from legendarr_backend.scheduling.job_timeout import configure_job_timeouts
from legendarr_backend.scheduling.queues import QUEUE_WORKERS, JobQueue
from legendarr_backend.scheduling.running_tasks import (
    RunningTaskRegistry,
    attach_running_task_registry,
    evict_stuck_tasks,
    evict_task,
    get_running_tasks,
    is_task_active,
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


def test_is_active_true_for_a_submitted_job():
    scheduler = _scheduler_with_job()
    registry = RunningTaskRegistry()
    registry.remember(_added_event("test_job"), scheduler)
    registry.submit(
        JobSubmissionEvent(EVENT_JOB_SUBMITTED, "test_job", "default", [datetime.now(UTC)]),
        scheduler,
    )

    assert registry.is_active("test_job") is True
    assert registry.is_active("other_job") is False


def test_is_active_false_once_the_job_finishes():
    scheduler = _scheduler_with_job()
    registry = RunningTaskRegistry()
    run_time = datetime.now(UTC)
    registry.remember(_added_event("test_job"), scheduler)
    registry.submit(
        JobSubmissionEvent(EVENT_JOB_SUBMITTED, "test_job", "default", [run_time]), scheduler
    )

    registry.finish(JobExecutionEvent(EVENT_JOB_EXECUTED, "test_job", "default", run_time))

    assert registry.is_active("test_job") is False


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


def test_tasks_flags_extra_submissions_as_queued_when_the_queue_has_two_workers():
    """The regression this exists to prevent: `scan_bulk` has exactly two workers
    (`scheduling/queues.py`), and the bulk fan-out submits one job per media file in a
    tight loop (`subtitle_discovery/jobs.py`'s `enqueue_full_subtitle_scan`) — only the
    first two should ever show as genuinely running at once.
    """
    scheduler = build_scheduler()
    registry = RunningTaskRegistry()
    for job_id in ("scan_1", "scan_2", "scan_3", "scan_4"):
        _register_and_submit(scheduler, registry, job_id, JobQueue.SCAN_BULK)

    assert {task.job_id: task.queued for task in registry.tasks()} == {
        "scan_1": False,
        "scan_2": False,
        "scan_3": True,
        "scan_4": True,
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


def test_tasks_uses_a_configured_worker_count_instead_of_the_queue_workers_default():
    """`scan_bulk` defaults to one worker, but a registry configured with a higher
    count (e.g. from `AppConfigFile.scan_bulk_queue_workers`) should treat that many
    submissions as genuinely running instead of falling back to the default."""
    scheduler = build_scheduler()
    registry = RunningTaskRegistry(queue_workers={JobQueue.SCAN_BULK: 2})
    for job_id in ("scan_1", "scan_2", "scan_3"):
        _register_and_submit(scheduler, registry, job_id, JobQueue.SCAN_BULK)

    assert {task.job_id: task.queued for task in registry.tasks()} == {
        "scan_1": False,
        "scan_2": False,
        "scan_3": True,
    }


def test_configure_overrides_an_existing_registrys_worker_counts():
    scheduler = build_scheduler()
    registry = RunningTaskRegistry()
    registry.configure({JobQueue.SCAN_BULK: 2})
    for job_id in ("scan_1", "scan_2"):
        _register_and_submit(scheduler, registry, job_id, JobQueue.SCAN_BULK)

    assert {task.job_id: task.queued for task in registry.tasks()} == {
        "scan_1": False,
        "scan_2": False,
    }


def test_clear_resets_configured_worker_counts_back_to_the_queue_workers_default():
    registry = RunningTaskRegistry(queue_workers={JobQueue.SCAN_BULK: 2})

    registry.clear()

    assert registry._queue_workers == QUEUE_WORKERS


def test_tasks_promotes_the_next_queued_job_once_the_running_one_finishes():
    scheduler = build_scheduler()
    registry = RunningTaskRegistry(queue_workers={JobQueue.SCAN_BULK: 1})
    first_run = _register_and_submit(scheduler, registry, "scan_1", JobQueue.SCAN_BULK)
    _register_and_submit(scheduler, registry, "scan_2", JobQueue.SCAN_BULK)
    assert {task.job_id: task.queued for task in registry.tasks()} == {
        "scan_1": False,
        "scan_2": True,
    }

    registry.finish(JobExecutionEvent(EVENT_JOB_EXECUTED, "scan_1", "default", first_run))

    assert {task.job_id: task.queued for task in registry.tasks()} == {"scan_2": False}


def _observe_running(registry: RunningTaskRegistry) -> None:
    """Let the registry see the task off the queue once, which is what stamps
    `running_since`. Nothing signals the queued-to-running transition — APScheduler emits
    an event on submission and on completion, never on start — so elapsed execution time
    only starts counting from the first observation. In production the UI polls every 3s
    and the stuck-task sweep every 15 minutes; in a test it has to be explicit."""
    registry.tasks()


def test_tasks_does_not_flag_a_fresh_task_as_stalled():
    scheduler = build_scheduler()
    registry = RunningTaskRegistry()
    _register_and_submit(scheduler, registry, "scan_1", JobQueue.SCAN_BULK)

    assert registry.tasks()[0].stalled is False


def test_tasks_measures_execution_time_from_when_a_task_left_the_queue(isolated_job_timeouts):
    """The regression this exists to prevent: a bulk fan-out submits thousands of jobs at
    once, so by the time one reaches a worker its `started_at` — really "submitted at" —
    can be hours old. Measuring from that would flag a job as stalled the instant it
    started, evict it, and let the next fan-out enqueue a duplicate of live work."""
    configure_job_timeouts({JobQueue.SCAN_BULK: 0.001})
    scheduler = build_scheduler()
    registry = RunningTaskRegistry(queue_workers={JobQueue.SCAN_BULK: 1})
    first_run = _register_and_submit(scheduler, registry, "scan_1", JobQueue.SCAN_BULK)
    _register_and_submit(scheduler, registry, "scan_2", JobQueue.SCAN_BULK)
    # `scan_2` waits behind `scan_1` for far longer than the queue's budget...
    _observe_running(registry)
    time.sleep(0.01)
    registry.finish(JobExecutionEvent(EVENT_JOB_EXECUTED, "scan_1", "default", first_run))

    # ...and is not stalled the moment it starts, however old its `started_at` is.
    started = {task.job_id: (task.queued, task.stalled) for task in registry.tasks()}

    assert started == {"scan_2": (False, False)}
    assert registry.evict_stuck(grace_seconds=0) == []


def test_tasks_flags_a_task_still_running_past_its_queues_budget_as_stalled(
    isolated_job_timeouts,
):
    """The state this exists to surface: a job blocked in a syscall never fires the
    `JobExecutionEvent` `finish()` waits for, so it stays "running" and holds its
    executor slot until the process restarts. Past its own queue's execution budget it is
    by definition a job whose budget didn't take, which is exactly what's worth flagging.
    """
    configure_job_timeouts({JobQueue.SCAN_BULK: 0.001})
    scheduler = build_scheduler()
    registry = RunningTaskRegistry()
    _register_and_submit(scheduler, registry, "scan_1", JobQueue.SCAN_BULK)
    _observe_running(registry)
    time.sleep(0.01)

    assert registry.tasks()[0].stalled is True


def test_tasks_falls_back_to_the_constant_threshold_when_the_queues_budget_is_off(
    isolated_job_timeouts, monkeypatch
):
    """A queue whose budget was turned off has no per-queue number to lean on, so the flat
    constant is what decides — the badge shouldn't silently stop working there."""
    monkeypatch.setattr(running_tasks_module, "STALLED_TASK_THRESHOLD_SECONDS", 0.0)
    configure_job_timeouts({JobQueue.SCAN_BULK: 0})
    scheduler = build_scheduler()
    registry = RunningTaskRegistry()
    _register_and_submit(scheduler, registry, "scan_1", JobQueue.SCAN_BULK)
    _observe_running(registry)

    assert registry.tasks()[0].stalled is True


def test_evict_stuck_leaves_a_queue_whose_budget_is_off_alone(isolated_job_timeouts, monkeypatch):
    """Setting a queue's budget to `0` is documented as removing its time limit — evicting
    on the fallback threshold anyway would kill exactly the long-but-healthy runs the
    escape hatch exists for. The badge still shows; only the eviction is withheld."""
    monkeypatch.setattr(running_tasks_module, "STALLED_TASK_THRESHOLD_SECONDS", 0.0)
    configure_job_timeouts({JobQueue.SCAN_BULK: 0})
    scheduler = build_scheduler()
    registry = RunningTaskRegistry()
    _register_and_submit(scheduler, registry, "scan_1", JobQueue.SCAN_BULK)
    _observe_running(registry)

    assert registry.tasks()[0].stalled is True
    assert registry.evict_stuck(grace_seconds=0) == []


def test_tasks_never_flags_a_queued_task_as_stalled(isolated_job_timeouts):
    """A queued task's `started_at` is really "submitted at", so elapsed time there says
    nothing about how long anything has been executing."""
    configure_job_timeouts({JobQueue.SCAN_BULK: 0.001})
    scheduler = build_scheduler()
    registry = RunningTaskRegistry(queue_workers={JobQueue.SCAN_BULK: 1})
    _register_and_submit(scheduler, registry, "scan_1", JobQueue.SCAN_BULK)
    _register_and_submit(scheduler, registry, "scan_2", JobQueue.SCAN_BULK)
    _observe_running(registry)
    time.sleep(0.01)

    assert {task.job_id: (task.queued, task.stalled) for task in registry.tasks()} == {
        "scan_1": (False, True),
        "scan_2": (True, False),
    }


def test_tasks_warns_about_a_stalled_task_only_once(isolated_job_timeouts, caplog):
    configure_job_timeouts({JobQueue.SCAN_BULK: 0.001})
    scheduler = build_scheduler()
    registry = RunningTaskRegistry()
    _register_and_submit(scheduler, registry, "scan_1", JobQueue.SCAN_BULK)
    _observe_running(registry)
    time.sleep(0.01)

    with caplog.at_level("WARNING", logger=running_tasks_module.__name__):
        registry.tasks()
        registry.tasks()

    warnings = [record for record in caplog.records if record.name == running_tasks_module.__name__]
    assert len(warnings) == 1
    assert "scan_1" in warnings[0].getMessage()


def test_evict_drops_every_entry_for_a_job_and_lets_it_be_enqueued_again():
    """The limbo this fixes: while the entry lives, `is_active` keeps every `enqueue_*`
    skipping that item, so a job whose completion event never arrives blocks its media
    file from ever being retried."""
    scheduler = build_scheduler()
    registry = RunningTaskRegistry()
    _register_and_submit(scheduler, registry, "scan_1", JobQueue.SCAN_BULK)
    _register_and_submit(scheduler, registry, "scan_2", JobQueue.SCAN_BULK)

    evicted = registry.evict("scan_1")

    assert [task.job_id for task in evicted] == ["scan_1"]
    assert registry.is_active("scan_1") is False
    assert registry.is_active("scan_2") is True


def test_evict_leaves_a_queued_entry_alone():
    """A queued entry hasn't started, so there's nothing stuck about it — recording one as
    an abandoned run would be a plain lie."""
    scheduler = build_scheduler()
    registry = RunningTaskRegistry(queue_workers={JobQueue.SCAN_BULK: 1})
    _register_and_submit(scheduler, registry, "scan_1", JobQueue.SCAN_BULK)
    _register_and_submit(scheduler, registry, "scan_1", JobQueue.SCAN_BULK)

    evicted = registry.evict("scan_1")

    assert len(evicted) == 1
    assert [task.queued for task in registry.tasks()] == [False]


def test_evict_for_a_job_that_isnt_running_returns_nothing():
    registry = RunningTaskRegistry()

    assert registry.evict("never_seen") == []


def test_evict_stuck_drops_a_running_task_past_its_grace_period(isolated_job_timeouts):
    configure_job_timeouts({JobQueue.SCAN_BULK: 0.001})
    scheduler = build_scheduler()
    registry = RunningTaskRegistry()
    _register_and_submit(scheduler, registry, "scan_1", JobQueue.SCAN_BULK)
    _observe_running(registry)
    time.sleep(0.01)

    evicted = registry.evict_stuck(grace_seconds=0)

    assert [task.job_id for task in evicted] == ["scan_1"]
    assert registry.tasks() == []


def test_evict_stuck_leaves_a_task_still_inside_its_grace_period_alone(isolated_job_timeouts):
    """A run merely slow to emit its completion event must not be declared abandoned."""
    configure_job_timeouts({JobQueue.SCAN_BULK: 0.001})
    scheduler = build_scheduler()
    registry = RunningTaskRegistry()
    _register_and_submit(scheduler, registry, "scan_1", JobQueue.SCAN_BULK)
    _observe_running(registry)
    time.sleep(0.01)

    assert registry.evict_stuck(grace_seconds=300) == []
    assert len(registry.tasks()) == 1


def test_evict_stuck_leaves_a_queued_task_alone(isolated_job_timeouts):
    """A queued task can legitimately sit there for as long as the work ahead of it takes
    — its `started_at` is "submitted at", not an elapsed-time anchor."""
    configure_job_timeouts({JobQueue.SCAN_BULK: 0.001})
    scheduler = build_scheduler()
    registry = RunningTaskRegistry(queue_workers={JobQueue.SCAN_BULK: 1})
    _register_and_submit(scheduler, registry, "scan_1", JobQueue.SCAN_BULK)
    _register_and_submit(scheduler, registry, "scan_2", JobQueue.SCAN_BULK)
    _observe_running(registry)
    time.sleep(0.01)

    evicted = registry.evict_stuck(grace_seconds=0)

    assert [task.job_id for task in evicted] == ["scan_1"]
    assert [task.job_id for task in registry.tasks()] == ["scan_2"]


def test_module_level_eviction_helpers_hit_the_shared_registry(
    isolated_running_tasks, isolated_job_timeouts
):
    configure_job_timeouts({JobQueue.SCAN_BULK: 0.001})
    scheduler = build_scheduler()
    attach_running_task_registry(scheduler)
    scheduler.start(paused=True)
    try:
        register_job(
            scheduler,
            _noop,
            queue=JobQueue.SCAN_BULK,
            job_id="scan_1",
            trigger="interval",
            minutes=1,
            retry_attempts=1,
            retry_delay_seconds=0,
            max_instances=1,
            coalesce=False,
        )
        running_tasks_module._registry.submit(
            JobSubmissionEvent(EVENT_JOB_SUBMITTED, "scan_1", "default", [datetime.now(UTC)]),
            scheduler,
        )
        assert is_task_active("scan_1") is True
        get_running_tasks()  # stamps `running_since` — see `_observe_running`
        time.sleep(0.01)

        assert [task.job_id for task in evict_stuck_tasks(grace_seconds=0)] == ["scan_1"]
        assert is_task_active("scan_1") is False
        assert evict_task("scan_1") == []
    finally:
        scheduler.shutdown(wait=False)


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


def test_attach_running_task_registry_applies_a_queue_workers_override():
    """`legendarr_backend.bootstrap.build_scheduler()` passes the same `queue_workers`
    map to both `scheduling.scheduler.build_scheduler()` and here — this is what keeps
    the "queued" badge honest once a queue's worker count is configured above its
    `QUEUE_WORKERS` default.
    """
    reset_running_tasks()
    scheduler = build_scheduler({JobQueue.SCAN_BULK: 2})
    attach_running_task_registry(scheduler, {JobQueue.SCAN_BULK: 2})
    scheduler.start()
    started = [threading.Event(), threading.Event()]
    finish = threading.Event()

    def slow_job(index: int) -> None:
        started[index].set()
        finish.wait(timeout=5)

    try:
        scheduler.add_job(slow_job, "date", args=[0], id="e2e_1", executor=JobQueue.SCAN_BULK.value)
        scheduler.add_job(slow_job, "date", args=[1], id="e2e_2", executor=JobQueue.SCAN_BULK.value)
        assert started[0].wait(timeout=5)
        assert started[1].wait(timeout=5)
        for _ in range(50):
            if len(get_running_tasks()) == 2:
                break
            time.sleep(0.02)
        tasks = get_running_tasks()
        assert {task.job_id: task.queued for task in tasks} == {
            "e2e_1": False,
            "e2e_2": False,
        }
    finally:
        finish.set()
        scheduler.shutdown(wait=False)
        reset_running_tasks()


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


def test_module_level_is_task_active_reflects_the_shared_registry():
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
        scheduler.add_job(slow_job, "date", id="e2e_active", executor=JobQueue.SYNC.value)
        assert started.wait(timeout=5)
        for _ in range(50):
            if is_task_active("e2e_active"):
                break
            time.sleep(0.02)

        assert is_task_active("e2e_active")
        assert not is_task_active("unknown_job")
    finally:
        finish.set()
        scheduler.shutdown(wait=False)
        reset_running_tasks()


def _added_event(job_id: str) -> JobEvent:
    return JobEvent(EVENT_JOB_ADDED, job_id, "default")
