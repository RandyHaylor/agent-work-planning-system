"""database_creation: creates database `planning_system` in the existing container if missing (CREATE
DATABASE outside a transaction, via the maintenance database on the same server), then migrates."""
from __future__ import annotations

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from planning_system.configuration import ConfigSection
from planning_system.server.storage import run_migrations

from .ports import DatabaseSetup

MAINTENANCE_DATABASE = "postgres"


class PostgresDatabaseSetup(DatabaseSetup):
    def __init__(self, storage_section: ConfigSection):
        self._section = storage_section

    def ensure_database(self):
        url = make_url(self._section.get("dsn"))
        name = url.database
        engine = create_engine(url.set(database=MAINTENANCE_DATABASE), isolation_level="AUTOCOMMIT")
        try:
            with engine.connect() as conn:
                exists = conn.execute(text("SELECT 1 FROM pg_database WHERE datname = :name"),
                                      {"name": name}).first() is not None
                if exists:
                    return False
                quoted = conn.dialect.identifier_preparer.quote_identifier(name)
                conn.execute(text(f"CREATE DATABASE {quoted}"))
                return True
        finally:
            engine.dispose()

    def migrate(self):
        run_migrations(self._section)
