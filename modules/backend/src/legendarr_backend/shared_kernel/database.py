from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlmodel import Session, create_engine

from legendarr_backend.shared_kernel.config import get_settings
from legendarr_backend.shared_kernel.config_file import load_or_create_config_file

_engine = None


def get_engine():
    global _engine
    if _engine is None:
        config = load_or_create_config_file(get_settings())
        _engine = create_engine(config.database_url, echo=False)
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
