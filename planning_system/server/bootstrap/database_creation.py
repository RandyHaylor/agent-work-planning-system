"""database_creation: creates database `planning_system` in the existing container if missing (CREATE
DATABASE outside a transaction, via the maintenance database on the same server), then migrates."""
from __future__ import annotations

from planning_system.configuration import ConfigSection

from .ports import DatabaseSetup


class PostgresDatabaseSetup(DatabaseSetup):
    def __init__(self, storage_section: ConfigSection):
        self._section = storage_section

    def ensure_database(self):
        raise NotImplementedError("level 7")

    def migrate(self):
        raise NotImplementedError("level 7")   # storage.run_migrations(self._section)
