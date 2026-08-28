import threading
import time
from datetime import UTC, datetime, timedelta

from apscheduler.events import (
    EVENT_JOB_ADDED,
    EVENT_JOB_ERROR,
    EVENT_JOB_MODIFIED,
    JobEvent,
    JobExecutionEvent,
)
from apscheduler.schedulers.background import BackgroundScheduler
from legendarr_backend.scheduling.queues import JobQueue
from legendarr_backend.scheduling.retry import with_retry
from legendarr_backend.scheduling.scheduled_retry import (
    BACKOFF_SCHEDULE,
    MAX_SCHEDULE_RETRIES,
    ScheduledRetryRegistry,
    attach_scheduled_retry,
    reset_scheduled_retries,
)
from legendarr_backend.scheduling.scheduler import build_scheduler, register_job


def _noop() -> None:
    pass


def _added_event(job_id: str) -> JobEvent:
    return JobEvent(EVENT_JOB_ADDED, job_id, "default")


def _modified_event(job_id: str) -> JobEvent:
    return JobEvent(EVENT_JOB_MODIFIED, job_id, "default")


def _error_event(job_id: str) -> JobExecutionEvent:
    return JobExecutionEvent(
        EVENT_JOB_ERROR,
        job_id,
        "default",
        scheduled_run_time=datetime.now(UTC),
        exception=ValueError("boom"),
    )


def _add_one_off(scheduler: BackgroundScheduler, job_id: str) -> None:
    scheduler.add_job(
        _noop,
        "date",
        id=job_id,
        name=job_id,
        executor=JobQueue.SYNC.value,
        max_instances=1,
        replace_existing=True,
        misfire_grace_time=None,
    )


def test_a_periodic_jobs_failure_is_left_alone():
    scheduler = build_scheduler()
    scheduler.start(paused=True)
    try:
        register_job(
            scheduler,
            _noop,
            queue=JobQueue.SYNC,
            job_id="periodic_job",
            trigger="interval",
            minutes=1,
            retry_attempts=1,
            retry_delay_seconds=0,
            max_instances=1,
            coalesce=True,
        )
        registry = ScheduledRetryRegistry()
        registry.remember(_added_event("periodic_job"), scheduler)
        original_job = scheduler.get_job("periodic_job")
        assert original_job is not None
        next_run_time = original_job.next_run_time

        registry.handle_error(_error_event("periodic_job"), scheduler)

        job = scheduler.get_job("periodic_job")
        assert job is not None
        assert job.next_run_time == next_run_time
    finally:
        scheduler.shutdown(wait=False)


def test_handle_error_for_a_job_never_cached_is_a_noop():
    scheduler = build_scheduler()
    scheduler.start(paused=True)
    try:
        registry = ScheduledRetryRegistry()

        registry.handle_error(_error_event("never_seen"), scheduler)

        assert scheduler.get_job("never_seen") is None
    finally:
        scheduler.shutdown(wait=False)


def test_a_one_off_jobs_failure_gets_rescheduled_with_backoff():
    scheduler = build_scheduler()
    scheduler.start(paused=True)
    try:
        registry = ScheduledRetryRegistry()
        _add_one_off(scheduler, "job1")
        registry.remember(_added_event("job1"), scheduler)
        scheduler.remove_job("job1")  # one-off jobs are already gone by error time

        before = datetime.now(UTC)
        registry.handle_error(_error_event("job1"), scheduler)

        job = scheduler.get_job("job1")
        assert job is not None
        assert job.next_run_time - before - BACKOFF_SCHEDULE[0] < timedelta(seconds=5)
    finally:
        scheduler.shutdown(wait=False)


def test_the_attempt_counter_survives_its_own_reschedule_and_increments():
    scheduler = build_scheduler()
    scheduler.start(paused=True)
    try:
        registry = ScheduledRetryRegistry()
        _add_one_off(scheduler, "job1")
        registry.remember(_added_event("job1"), scheduler)

        for backoff in BACKOFF_SCHEDULE:
            scheduler.remove_job("job1")
            before = datetime.now(UTC)
            registry.handle_error(_error_event("job1"), scheduler)
            job = scheduler.get_job("job1")
            assert job is not None
            assert job.next_run_time - before - backoff < timedelta(seconds=5)

        # One more failure than MAX_SCHEDULE_RETRIES allows: give up for good.
        scheduler.remove_job("job1")
        registry.handle_error(_error_event("job1"), scheduler)
        assert scheduler.get_job("job1") is None
    finally:
        scheduler.shutdown(wait=False)


def test_after_max_schedule_retries_the_failure_just_stands():
    scheduler = build_scheduler()
    scheduler.start(paused=True)
    try:
        registry = ScheduledRetryRegistry()
        _add_one_off(scheduler, "job1")
        registry.remember(_added_event("job1"), scheduler)

        for _ in range(MAX_SCHEDULE_RETRIES):
            scheduler.remove_job("job1")
            registry.handle_error(_error_event("job1"), scheduler)

        scheduler.remove_job("job1")
        registry.handle_error(_error_event("job1"), scheduler)

        assert scheduler.get_job("job1") is None
    finally:
        scheduler.shutdown(wait=False)


def test_a_fresh_reenqueue_while_a_backoff_retry_is_pending_resets_the_budget():
    scheduler = build_scheduler()
    scheduler.start(paused=True)
    try:
        registry = ScheduledRetryRegistry()
        _add_one_off(scheduler, "job1")
        registry.remember(_added_event("job1"), scheduler)
        scheduler.remove_job("job1")
        registry.handle_error(_error_event("job1"), scheduler)  # first backed-off retry queued

        # User re-triggers the same action (e.g. clicks "Translate" again) while that
        # backed-off retry is still pending — same job_id, replaces the pending one.
        _add_one_off(scheduler, "job1")
        registry.remember(_modified_event("job1"), scheduler)
        scheduler.remove_job("job1")

        before = datetime.now(UTC)
        registry.handle_error(_error_event("job1"), scheduler)

        job = scheduler.get_job("job1")
        assert job is not None
        assert job.next_run_time - before - BACKOFF_SCHEDULE[0] < timedelta(seconds=5)
    finally:
        scheduler.shutdown(wait=False)


def test_end_to_end_a_real_one_off_jobs_failure_gets_a_backed_off_follow_up():
    """No synthetic events: a real one-off job that exhausts `with_retry` should show up
    again in the jobstore under the same id, scheduled a few minutes out."""
    reset_scheduled_retries()
    scheduler = build_scheduler()
    attach_scheduled_retry(scheduler)
    scheduler.start()
    failed = threading.Event()

    def failing_job() -> None:
        failed.set()
        raise ValueError("boom")

    try:
        scheduler.add_job(
            with_retry(failing_job, max_attempts=1, delay_seconds=0),
            "date",
            id="e2e_one_off",
            name="e2e_one_off",
            executor=JobQueue.SYNC.value,
            max_instances=1,
            replace_existing=True,
            misfire_grace_time=None,
        )
        assert failed.wait(timeout=5)

        job = None
        for _ in range(50):
            job = scheduler.get_job("e2e_one_off")
            if job is not None:
                break
            time.sleep(0.05)

        assert job is not None
        assert job.next_run_time > datetime.now(UTC) + timedelta(minutes=1)
    finally:
        scheduler.shutdown(wait=False)
        reset_scheduled_retries()
