import yaml
from legendarr_backend.config.config_file import load_or_create_config_file
from legendarr_backend.config.settings import Settings
from legendarr_backend.security.secrets import ENCRYPTED_PREFIX


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


def test_api_keys_are_encrypted_on_disk_but_returned_as_plaintext(tmp_path):
    settings = Settings(
        data_dir=tmp_path,
        database_url="",
        radarr_api_key="radarr-key",
        sonarr_api_key="sonarr-key",
    )

    config = load_or_create_config_file(settings)

    assert config.radarr_api_key == "radarr-key"
    assert config.sonarr_api_key == "sonarr-key"

    stored = yaml.safe_load((tmp_path / "config.yaml").read_text())
    assert stored["radarr_api_key"].startswith(ENCRYPTED_PREFIX)
    assert stored["sonarr_api_key"].startswith(ENCRYPTED_PREFIX)
    assert "radarr-key" not in stored["radarr_api_key"]
    assert "sonarr-key" not in stored["sonarr_api_key"]


def test_already_encrypted_config_file_is_not_rewritten(tmp_path):
    settings = Settings(data_dir=tmp_path, database_url="", radarr_api_key="radarr-key")
    load_or_create_config_file(settings)
    written_once = (tmp_path / "config.yaml").read_text()

    config = load_or_create_config_file(settings)

    assert (tmp_path / "config.yaml").read_text() == written_once
    assert config.radarr_api_key == "radarr-key"


def test_legacy_plaintext_api_keys_are_read_and_reencrypted_on_disk(tmp_path):
    settings = Settings(data_dir=tmp_path, database_url="")
    load_or_create_config_file(settings)  # establishes schema + key file
    (tmp_path / "config.yaml").write_text(
        "radarr_api_key: legacy-radarr-key\nsonarr_api_key: legacy-sonarr-key\n"
    )

    config = load_or_create_config_file(settings)

    assert config.radarr_api_key == "legacy-radarr-key"
    assert config.sonarr_api_key == "legacy-sonarr-key"
    stored = yaml.safe_load((tmp_path / "config.yaml").read_text())
    assert stored["radarr_api_key"].startswith(ENCRYPTED_PREFIX)
    assert stored["sonarr_api_key"].startswith(ENCRYPTED_PREFIX)
