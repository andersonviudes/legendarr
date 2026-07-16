from logging.config import fileConfig

from alembic import context
from legendarr_backend.language_profiles import models as language_profiles_models  # noqa: F401
from legendarr_backend.shared_kernel.config.config_file import load_or_create_config_file
from legendarr_backend.shared_kernel.config.settings import get_settings
from sqlalchemy import engine_from_config, pool
from sqlmodel import SQLModel

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

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
