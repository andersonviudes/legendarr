from logging.config import fileConfig

from alembic import context
from legendarr_backend.arr_services import models as arr_services_models  # noqa: F401
from legendarr_backend.authentication import models as authentication_models  # noqa: F401
from legendarr_backend.config.config_file import load_or_create_config_file
from legendarr_backend.config.settings import get_settings
from legendarr_backend.language_profiles import models as language_profiles_models  # noqa: F401
from legendarr_backend.media_library import models as media_library_models  # noqa: F401
from legendarr_backend.media_metadata import models as media_metadata_models  # noqa: F401
from legendarr_backend.media_servers import models as media_servers_models  # noqa: F401
from legendarr_backend.subtitle_acquisition import (
    models as subtitle_acquisition_models,  # noqa: F401
)
from legendarr_backend.subtitle_discovery import models as subtitle_discovery_models  # noqa: F401
from legendarr_backend.subtitle_translation import (
    models as subtitle_translation_models,  # noqa: F401
)
from legendarr_backend.system import models as system_models  # noqa: F401
from sqlalchemy import engine_from_config, pool
from sqlmodel import SQLModel

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
# `database/engine.py::init_db()` (the programmatic path — the real running app, plus
# every test that goes through `isolated_database`) passes `configure_logger: False` in
# `config.attributes` to skip this: the app already configured the root logger itself
# (`legendarr_backend/logging/setup.py::configure_logging()`), and `fileConfig()` here
# would silently replace its handlers with `alembic.ini`'s own (stderr, WARNING) *and*
# disable every already-imported module logger process-wide (`disable_existing_loggers`
# defaults to `True`) — breaking both the System page's log viewer and pytest's `caplog`
# for the rest of the process. Bare `alembic` CLI invocations (no `attributes` set) are
# unaffected and still get logging configured here, same as before.
if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# every SQLModel table module is imported above so its tables register on
# SQLModel.metadata before autogenerate compares against it
target_metadata = SQLModel.metadata

# programmatic invocations (database/engine.py's init_db()) already set sqlalchemy.url
# on this Config before calling us, targeting a specific engine; only resolve it
# ourselves for standalone `alembic` CLI invocations, where it's still unset
if not config.get_main_option("sqlalchemy.url"):
    config.set_main_option(
        "sqlalchemy.url", load_or_create_config_file(get_settings()).database_url
    )


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
