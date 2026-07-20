from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import event
from sqlmodel import Session, create_engine

from legendarr_backend.config.config_file import load_or_create_config_file
from legendarr_backend.config.settings import get_settings

_engine = None


def enable_sqlite_foreign_keys(dbapi_connection, connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def get_engine():
    global _engine
    if _engine is None:
        config = load_or_create_config_file(get_settings())
        _engine = create_engine(config.database_url, echo=False)
        # SQLite ignores FK constraints (including our ON DELETE CASCADE/SET NULL) unless
        # enforcement is turned on per-connection — there's no server-wide setting for it.
        if _engine.dialect.name == "sqlite":
            event.listen(_engine, "connect", enable_sqlite_foreign_keys)
    return _engine


def init_db() -> None:
    engine = get_engine()
    alembic_cfg = Config(str(Path(__file__).resolve().parents[3] / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", engine.url.render_as_string(hide_password=False))
    command.upgrade(alembic_cfg, "head")


@contextmanager
def get_session() -> Iterator[Session]:
    with Session(get_engine()) as session:
        yield session
