from legendarr_backend import bootstrap
from legendarr_backend.config.config_file import AppConfigFile


def test_build_scheduler_registers_media_sync_job(monkeypatch):
    monkeypatch.setattr(bootstrap, "init_db", lambda: None)
    monkeypatch.setattr(bootstrap, "load_or_create_config_file", lambda settings: AppConfigFile())

    scheduler = bootstrap.build_scheduler()

    assert scheduler.get_job("media_library_sync") is not None
