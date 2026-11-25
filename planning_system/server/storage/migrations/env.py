"""Alembic environment: target_metadata = METADATA (every store's tables). The URL comes from the
`sqlalchemy.url` option run_migrations sets from the storage config section."""
from alembic import context
from sqlalchemy import engine_from_config, pool

import planning_system.server.storage  # noqa: F401  (imports every store, declaring its tables)
from planning_system.server.storage.metadata import METADATA

config = context.config
target_metadata = METADATA


def run_migrations_offline() -> None:
    context.configure(url=config.get_main_option("sqlalchemy.url"), target_metadata=target_metadata,
                      literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(config.get_section(config.config_ini_section, {}),
                                     prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
