from legendarr_backend.config.config_file import load_or_create_config_file
from legendarr_backend.config.settings import Settings


def test_creates_config_file_with_env_derived_defaults(tmp_path):
    settings = Settings(
        data_dir=tmp_path,
        database_url="",
        radarr_url="http://radarr:7878",
        radarr_api_key="radarr-key",
        sonarr_url="http://sonarr:8989",
        sonarr_api_key="sonarr-key",
        sync_interval_minutes=30,
        sync_retry_attempts=4,
        sync_retry_delay_seconds=2.5,
        sync_max_instances=2,
        sync_coalesce=False,
    )

    config = load_or_create_config_file(settings)

    assert config.database_url == settings.resolved_database_url
    assert config.radarr_url == "http://radarr:7878"
    assert config.radarr_api_key == "radarr-key"
    assert config.sonarr_url == "http://sonarr:8989"
    assert config.sonarr_api_key == "sonarr-key"
    assert config.sync_interval_minutes == 30
    assert config.sync_retry_attempts == 4
    assert config.sync_retry_delay_seconds == 2.5
    assert config.sync_max_instances == 2
    assert config.sync_coalesce is False
    assert (tmp_path / "config.yaml").exists()


def test_reads_existing_config_file_back_unchanged(tmp_path):
    settings = Settings(data_dir=tmp_path, database_url="", radarr_url="http://radarr:7878")
    (tmp_path / "config.yaml").write_text(
        "database_url: sqlite:////custom/path.db\n"
        "radarr_url: http://other-radarr:7878\n"
        "radarr_api_key: other-key\n"
        "sonarr_url: ''\n"
        "sonarr_api_key: ''\n"
        "sync_interval_minutes: 60\n"
        "sync_retry_attempts: 7\n"
        "sync_retry_delay_seconds: 1.5\n"
        "sync_max_instances: 4\n"
        "sync_coalesce: false\n"
    )

    config = load_or_create_config_file(settings)

    assert config.database_url == "sqlite:////custom/path.db"
    assert config.radarr_url == "http://other-radarr:7878"
    assert config.sync_interval_minutes == 60
    assert config.sync_retry_attempts == 7
    assert config.sync_retry_delay_seconds == 1.5
    assert config.sync_max_instances == 4
    assert config.sync_coalesce is False


def test_backfills_missing_fields_from_settings_and_rewrites_file(tmp_path):
    settings = Settings(
        data_dir=tmp_path,
        database_url="",
        radarr_url="http://radarr:7878",
        radarr_api_key="radarr-key",
        sync_interval_minutes=45,
    )
    (tmp_path / "config.yaml").write_text("database_url: sqlite:////custom/path.db\n")

    config = load_or_create_config_file(settings)

    assert config.database_url == "sqlite:////custom/path.db"
    assert config.radarr_url == "http://radarr:7878"
    assert config.radarr_api_key == "radarr-key"
    assert config.sync_interval_minutes == 45

    rewritten = (tmp_path / "config.yaml").read_text()
    assert "radarr_url: http://radarr:7878" in rewritten
