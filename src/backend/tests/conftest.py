import os
import tempfile

import pytest

# Every table module must register on SQLModel.metadata before `in_memory_session`
# calls create_all — importing them here instead of relying on whichever test module
# happened to be collected first (FK resolution fails otherwise, e.g. movie ->
# languageprofile when only media_library.models was imported).
from legendarr_backend.arr_services import models as _arr_services_models  # noqa: F401
from legendarr_backend.authentication import models as _authentication_models  # noqa: F401
from legendarr_backend.config.settings import Settings
from legendarr_backend.database import engine as database
from legendarr_backend.database.engine import enable_sqlite_foreign_keys
from legendarr_backend.language_profiles import models as _language_profiles_models  # noqa: F401
from legendarr_backend.logging.setup import reset_log_records
from legendarr_backend.media_library import models as _media_library_models  # noqa: F401
from legendarr_backend.media_metadata import models as _media_metadata_models  # noqa: F401
from legendarr_backend.scheduling.running_tasks import reset_running_tasks
from legendarr_backend.subtitle_acquisition import (
    models as _subtitle_acquisition_models,  # noqa: F401
)
from legendarr_backend.subtitle_discovery import models as _subtitle_discovery_models  # noqa: F401
from legendarr_backend.subtitle_translation import (
    models as _subtitle_translation_models,  # noqa: F401
)
from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine


@pytest.fixture(autouse=True, scope="session")
def _isolated_data_dir():
    with tempfile.TemporaryDirectory() as tmp_dir:
        os.environ["LEGENDARR_DATA_DIR"] = tmp_dir
        yield


@pytest.fixture(autouse=True)
def _no_real_embedded_subtitle_probing(monkeypatch):
    """Never invoke a real `ffprobe` subprocess from a test by default — same isolation
    principle as never making a real HTTP call in a test. Tests exercising the probe/extract
    mechanics directly (`subtitle_discovery`'s probe/scan tests) monkeypatch these targets
    themselves, which simply overrides this default within that test."""
    monkeypatch.setattr(
        "legendarr_backend.subtitle_discovery.scan_video_subtitles.probe_embedded_subtitle_tracks",
        lambda *args, **kwargs: [],
    )


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
def isolated_log_buffer():
    """Reset the in-memory log ring buffer so assertions on recent log lines aren't
    affected by lines emitted by other tests running in the same process."""
    reset_log_records()
    yield
    reset_log_records()


@pytest.fixture
def isolated_running_tasks():
    """Reset the in-memory running-task registry so assertions on it aren't affected by
    jobs submitted by other tests running in the same process."""
    reset_running_tasks()
    yield
    reset_running_tasks()


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
