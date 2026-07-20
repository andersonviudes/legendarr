import os
import tempfile

import pytest
from legendarr_backend.config.settings import Settings
from legendarr_backend.database import engine as database
from legendarr_backend.database.engine import enable_sqlite_foreign_keys
from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine


@pytest.fixture(autouse=True, scope="session")
def _isolated_data_dir():
    with tempfile.TemporaryDirectory() as tmp_dir:
        os.environ["LEGENDARR_DATA_DIR"] = tmp_dir
        yield


@pytest.fixture
def isolated_database(tmp_path, monkeypatch) -> Settings:
    """Point `database.engine` at a fresh on-disk SQLite DB under `tmp_path`.

    Use for tests that go through the real `init_db()`/Alembic path (e.g. the API or
    `init_db()` itself). For tests that only need a `Session` against the current schema,
    prefer `in_memory_session`.
    """
    settings = Settings(data_dir=tmp_path, database_url="")
    monkeypatch.setattr(database, "get_settings", lambda: settings)
    monkeypatch.setattr(database, "_engine", None)
    return settings


@pytest.fixture
def in_memory_session():
    """A `Session` bound to a fresh in-memory SQLite DB with all tables created.

    Bypasses Alembic entirely (schema is created straight from `SQLModel.metadata`) — for
    tests of slice service functions that only need a working `Session`, not the real
    migration path.
    """
    engine = create_engine("sqlite://")
    event.listen(engine, "connect", enable_sqlite_foreign_keys)
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        yield session
