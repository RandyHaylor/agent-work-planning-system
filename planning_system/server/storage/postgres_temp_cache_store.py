"""postgres_temp_cache_store: implements references' TempCacheStoragePort. Declares
temp_cache_entries; clearing the cache touches no other table."""
from __future__ import annotations

from sqlalchemy import JSON, Column, DateTime, Table, Text
from sqlalchemy.engine import Connection

from planning_system.server.domain.references.ports import TempCacheStoragePort

from .metadata import METADATA

TEMP_CACHE_ENTRIES = Table(
    "temp_cache_entries", METADATA,
    Column("cache_id", Text, primary_key=True),
    Column("owner", Text, nullable=False, index=True),
    Column("text", Text, nullable=False),
    Column("sha256", Text, nullable=False, index=True),
    Column("created_at", DateTime(timezone=True), nullable=False, index=True),
    Column("metadata", JSON, nullable=False),
)


class PostgresTempCacheStore(TempCacheStoragePort):
    def __init__(self, conn: Connection):
        self._conn = conn

    def get(self, cache_id):
        raise NotImplementedError("level 7")

    def save(self, entry):
        raise NotImplementedError("level 7")

    def delete(self, cache_id):
        raise NotImplementedError("level 7")

    def created_before(self, cutoff):
        raise NotImplementedError("level 7")
