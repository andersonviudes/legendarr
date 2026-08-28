from contextlib import contextmanager

from legendarr_backend.config.config_file import AppConfigFile
from legendarr_backend.maintenance import jobs as jobs_module
from legendarr_backend.maintenance.jobs import register_temp_file_cleanup_job
from legendarr_backend.scheduling.queues import JobQueue
from legendarr_backend.scheduling.scheduler import build_scheduler


def test_register_temp_file_cleanup_job_wires_config_derived_policy():
    scheduler = build_scheduler()
    config = AppConfigFile(
        temp_file_cleanup_interval_minutes=60,
        temp_file_cleanup_max_instances=2,
        temp_file_cleanup_coalesce=False,
    )

    register_temp_file_cleanup_job(scheduler, config)

    job = scheduler.get_job("maintenance_temp_file_cleanup")
    assert job is not None
    assert job.executor == JobQueue.MAINTENANCE.value
    assert job.max_instances == 2
    assert job.coalesce is False
    assert job.trigger.interval.total_seconds() == 60 * 60


def test_temp_file_cleanup_job_sweep_calls_cleanup_orphaned_temp_files(monkeypatch):
    calls: list[tuple[object, dict]] = []
    monkeypatch.setattr(
        jobs_module,
        "cleanup_orphaned_temp_files",
        lambda session, **kwargs: calls.append((session, kwargs)) or 3,
    )

    @contextmanager
    def _session():
        yield "the-session"

    monkeypatch.setattr(jobs_module, "get_session", _session)
    scheduler = build_scheduler()
    config = AppConfigFile(
        temp_file_cleanup_interval_minutes=1, temp_file_cleanup_min_age_minutes=45
    )

    register_temp_file_cleanup_job(scheduler, config)
    job = scheduler.get_job("maintenance_temp_file_cleanup")
    assert job is not None
    job.func()

    assert calls == [("the-session", {"min_age_minutes": 45})]

    job.func()  # must not raise
