from legendarr_backend import bootstrap
from legendarr_backend.config.config_file import AppConfigFile
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
