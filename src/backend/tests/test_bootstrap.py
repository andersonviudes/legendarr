import yaml
from legendarr_backend import bootstrap
from legendarr_backend.config.config_file import AppConfigFile
from legendarr_backend.scheduling.job_timeout import job_timeout_seconds
from legendarr_backend.scheduling.queues import JobQueue


def test_build_scheduler_registers_media_sync_job(monkeypatch):
    monkeypatch.setattr(bootstrap, "init_db", lambda: None)
    monkeypatch.setattr(bootstrap, "load_or_create_config_file", lambda settings: AppConfigFile())

    scheduler = bootstrap.build_scheduler()

    assert scheduler.get_job("media_library_sync") is not None


def test_build_scheduler_sizes_queues_from_config(monkeypatch):
    monkeypatch.setattr(bootstrap, "init_db", lambda: None)
    monkeypatch.setattr(
        bootstrap,
        "load_or_create_config_file",
        lambda settings: AppConfigFile(scan_queue_workers=7, scan_bulk_queue_workers=3),
    )

    scheduler = bootstrap.build_scheduler()

    assert scheduler._executors[JobQueue.SCAN.value]._pool._max_workers == 7
    assert scheduler._executors[JobQueue.SCAN_BULK.value]._pool._max_workers == 3


def test_build_scheduler_registers_the_stuck_task_sweep(monkeypatch):
    monkeypatch.setattr(bootstrap, "init_db", lambda: None)
    monkeypatch.setattr(bootstrap, "load_or_create_config_file", lambda settings: AppConfigFile())

    scheduler = bootstrap.build_scheduler()

    assert scheduler.get_job("maintenance_stuck_task_sweep") is not None


def test_build_scheduler_applies_the_configured_execution_budgets(
    monkeypatch, isolated_job_timeouts
):
    """The composition root is the only place a `config.yaml` value reaches
    `job_timeout_seconds` — what `scheduling/scheduler.py` then reads for every job it
    registers (covered on its own in `tests/scheduling/test_scheduler.py`)."""
    monkeypatch.setattr(bootstrap, "init_db", lambda: None)
    monkeypatch.setattr(
        bootstrap,
        "load_or_create_config_file",
        lambda settings: AppConfigFile(
            sync_job_timeout_seconds=42, acquire_bulk_job_timeout_seconds=7
        ),
    )

    bootstrap.build_scheduler()

    assert job_timeout_seconds(JobQueue.SYNC) == 42
    assert job_timeout_seconds(JobQueue.ACQUIRE_BULK) == 7


def test_a_fresh_config_file_carries_every_queues_execution_budget(isolated_database):
    """A real `config.yaml`, not an `AppConfigFile()` built in a test, must end up with one
    budget key per `JobQueue` — that file is the source of truth once it exists, so a queue
    missing from it is a queue nobody can ever tune."""
    bootstrap.load_or_create_config_file(isolated_database)

    stored = yaml.safe_load((isolated_database.data_dir / "config.yaml").read_text())

    for queue in JobQueue:
        assert stored[f"{queue.value}_job_timeout_seconds"] > 0
