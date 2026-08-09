from legendarr_backend.scheduling.queues import JobQueue
from legendarr_backend.scheduling.scheduler import build_scheduler, register_job


def _noop() -> None:
    pass


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
    assert job.executor == JobQueue.SYNC.value
    assert job.max_instances == 2
    assert job.coalesce is False


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
