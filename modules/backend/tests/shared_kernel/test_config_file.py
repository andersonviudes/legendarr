from legendarr_backend.shared_kernel.config import Settings
from legendarr_backend.shared_kernel.config_file import load_or_create_config_file


def test_creates_config_file_with_env_derived_default(tmp_path):
    settings = Settings(data_dir=tmp_path, database_url="")

    config = load_or_create_config_file(settings)

    assert config.database_url == settings.resolved_database_url
    assert (tmp_path / "config.yaml").exists()


def test_reads_existing_config_file_back_unchanged(tmp_path):
    settings = Settings(data_dir=tmp_path, database_url="")
    (tmp_path / "config.yaml").write_text("database_url: sqlite:////custom/path.db\n")

    config = load_or_create_config_file(settings)

    assert config.database_url == "sqlite:////custom/path.db"
