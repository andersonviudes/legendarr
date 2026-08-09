from legendarr_backend.database import engine as database
from sqlalchemy import text


def test_init_db_creates_schema_via_alembic(isolated_database):
    database.init_db()

    with database.get_engine().connect() as connection:
        tables = {
            row[0]
            for row in connection.execute(text("select name from sqlite_master where type='table'"))
        }

    assert "languageprofile" in tables
    assert "alembic_version" in tables
