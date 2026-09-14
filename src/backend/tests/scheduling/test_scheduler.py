import threading

import pytest
from legendarr_backend.scheduling.job_timeout import JobTimeoutError, configure_job_timeouts
from legendarr_backend.scheduling.queues import QUEUE_WORKERS, JobQueue
from legendarr_backend.scheduling.scheduler import (
    JOB_JITTER_SECONDS,
    build_scheduler,
    register_adhoc_job,
    register_job,
)


def _noop() -> None:
    pass


def _pool_size(scheduler, queue: JobQueue) -> int:
    return scheduler._executors[queue.value]._pool._max_workers


def test_build_scheduler_defaults_every_queue_to_queue_workers():
    scheduler = build_scheduler()

    for queue, workers in QUEUE_WORKERS.items():
        assert _pool_size(scheduler, queue) == workers


def test_build_scheduler_overrides_a_queues_worker_count():
    scheduler = build_scheduler({JobQueue.SCAN: 5})

    assert _pool_size(scheduler, JobQueue.SCAN) == 5


def test_build_scheduler_falls_back_to_queue_workers_for_queues_missing_from_the_override():
    scheduler = build_scheduler({JobQueue.SCAN: 5})

    assert _pool_size(scheduler, JobQueue.SCAN_BULK) == QUEUE_WORKERS[JobQueue.SCAN_BULK]


def test_register_job_applies_queue_and_concurrency_policy():
    scheduler = build_scheduler()

    register_job(
        scheduler,
        _noop,
        queue=JobQueue.SYNC,
        job_id="test_job",
        trigger="interval",
        minutes=1,
        retry_attempts=1,
        retry_delay_seconds=0,
        max_instances=2,
        coalesce=False,
    )

    job = scheduler.get_job("test_job")
    assert job is not None
    assert job.executor == JobQueue.SYNC.value
    assert job.max_instances == 2
    assert job.coalesce is False


def test_register_job_defaults_to_a_jitter():
    scheduler = build_scheduler()

    register_job(
        scheduler,
        _noop,
        queue=JobQueue.SYNC,
        job_id="test_job",
        trigger="interval",
        minutes=1,
        retry_attempts=1,
        retry_delay_seconds=0,
        max_instances=1,
        coalesce=True,
    )

    job = scheduler.get_job("test_job")
    assert job is not None
    assert job.trigger.jitter == JOB_JITTER_SECONDS


def test_register_job_lets_caller_override_jitter():
    scheduler = build_scheduler()

    register_job(
        scheduler,
        _noop,
        queue=JobQueue.SYNC,
        job_id="test_job",
        trigger="interval",
        minutes=1,
        jitter=5,
        retry_attempts=1,
        retry_delay_seconds=0,
        max_instances=1,
        coalesce=True,
    )

    job = scheduler.get_job("test_job")
    assert job is not None
    assert job.trigger.jitter == 5


def test_register_job_with_same_id_replaces_existing_job():
    scheduler = build_scheduler()
    # Dedup happens when a job is flushed into the jobstore, which only happens once the
    # scheduler starts — registering twice before that just queues two pending adds.
    scheduler.start(paused=True)

    try:
        for _ in range(2):
            register_job(
                scheduler,
                _noop,
                queue=JobQueue.SYNC,
                job_id="test_job",
                trigger="interval",
                minutes=1,
                retry_attempts=1,
                retry_delay_seconds=0,
                max_instances=1,
                coalesce=True,
            )

        assert len(scheduler.get_jobs()) == 1
    finally:
        scheduler.shutdown(wait=False)


def test_register_adhoc_job_applies_the_one_off_enqueue_shape():
    scheduler = build_scheduler()

    register_adhoc_job(
        scheduler,
        _noop,
        queue=JobQueue.ACQUIRE,
        job_id="test_adhoc_job",
        retry_attempts=1,
        retry_delay_seconds=0,
    )

    job = scheduler.get_job("test_adhoc_job")
    assert job is not None
    assert job.executor == JobQueue.ACQUIRE.value
    assert job.max_instances == 1
    assert job.misfire_grace_time is None


def test_register_adhoc_job_keeps_the_cascade_flag_readable_off_the_registered_job():
    """The sticky-cascade merge in `subtitle_acquisition/jobs.py` (and its two siblings)
    reads `scheduler.get_job(job_id).func.cascade`, so neither the retry wrapper nor the
    execution-budget wrapper may hide it."""
    scheduler = build_scheduler()

    def work() -> None:
        pass

    work.cascade = True  # type: ignore[attr-defined]

    register_adhoc_job(
        scheduler,
        work,
        queue=JobQueue.ACQUIRE,
        job_id="test_cascade_job",
        retry_attempts=1,
        retry_delay_seconds=0,
    )

    job = scheduler.get_job("test_cascade_job")
    assert job is not None
    assert getattr(job.func, "cascade", False) is True


def test_registered_job_runs_under_its_queues_execution_budget(isolated_job_timeouts):
    """A job that overruns fails instead of holding its worker thread forever — the whole
    reason a wedged job used to take a queue's capacity down until the process restarted."""
    configure_job_timeouts({JobQueue.SCAN: 0.05})
    scheduler = build_scheduler()
    release = threading.Event()

    def slow() -> None:
        release.wait(timeout=30)

    register_adhoc_job(
        scheduler,
        slow,
        queue=JobQueue.SCAN,
        job_id="test_slow_job",
        retry_attempts=1,
        retry_delay_seconds=0,
    )

    job = scheduler.get_job("test_slow_job")
    assert job is not None
    try:
        with pytest.raises(JobTimeoutError):
            job.func()
    finally:
        release.set()
