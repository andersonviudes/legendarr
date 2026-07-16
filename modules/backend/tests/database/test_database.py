from legendarr_backend.config.settings import Settings
from legendarr_backend.database import engine as database
from sqlalchemy import text


def test_init_db_creates_schema_via_alembic(tmp_path, monkeypatch):
    settings = Settings(data_dir=tmp_path, database_url="")
    monkeypatch.setattr(database, "get_settings", lambda: settings)
    monkeypatch.setattr(database, "_engine", None)

    database.init_db()

    with database.get_engine().connect() as connection:
        tables = {
            row[0]
            for row in connection.execute(text("select name from sqlite_master where type='table'"))
        }

    assert "languageprofile" in tables
    assert "alembic_version" in tables
