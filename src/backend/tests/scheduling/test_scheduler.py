from legendarr_backend.scheduling.queues import QUEUE_WORKERS, JobQueue
from legendarr_backend.scheduling.scheduler import JOB_JITTER_SECONDS, build_scheduler, register_job


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
