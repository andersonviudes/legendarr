from legendarr_backend.config.config_file import AppConfigFile
from legendarr_backend.media_library.jobs import register_sync_job
from legendarr_backend.scheduling.queues import JobQueue
from legendarr_backend.scheduling.scheduler import build_scheduler


def test_register_sync_job_wires_config_derived_policy():
    scheduler = build_scheduler()
    config = AppConfigFile(
        sync_interval_minutes=30,
        sync_retry_attempts=5,
        sync_retry_delay_seconds=2.0,
        sync_max_instances=3,
        sync_coalesce=False,
    )

    register_sync_job(scheduler, config)

    job = scheduler.get_job("media_library_sync")
    assert job is not None
    assert job.executor == JobQueue.SYNC.value
    assert job.max_instances == 3
    assert job.coalesce is False
    assert job.trigger.interval.total_seconds() == 30 * 60
