"""postgres_temp_cache_store: implements references' TempCacheStoragePort. Declares
temp_cache_entries; clearing the cache touches no other table."""
from __future__ import annotations

from sqlalchemy import JSON, Column, DateTime, Table, Text
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Connection

from planning_system.server.domain.references import TempCacheStoragePort
from planning_system.server.domain.references import TempCacheEntry

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
        found = self._entries(select(TEMP_CACHE_ENTRIES).where(TEMP_CACHE_ENTRIES.c.cache_id == cache_id))
        return found[0] if found else None

    def save(self, entry):
        row = dict(cache_id=entry.cache_id, owner=entry.owner, text=entry.text, sha256=entry.sha256,
                   created_at=entry.created_at, metadata=dict(entry.metadata))
        statement = insert(TEMP_CACHE_ENTRIES).values(**row)
        self._conn.execute(statement.on_conflict_do_update(
            index_elements=[TEMP_CACHE_ENTRIES.c.cache_id],
            set_={k: statement.excluded[k] for k in row if k != "cache_id"}))

    def delete(self, cache_id):
        self._conn.execute(TEMP_CACHE_ENTRIES.delete().where(TEMP_CACHE_ENTRIES.c.cache_id == cache_id))

    def created_before(self, cutoff):
        return self._entries(select(TEMP_CACHE_ENTRIES).where(TEMP_CACHE_ENTRIES.c.created_at < cutoff)
                             .order_by(TEMP_CACHE_ENTRIES.c.created_at))

    def _entries(self, statement):
        return [TempCacheEntry(r.cache_id, r.owner, r.text, r.sha256, r.created_at, dict(r.metadata))
                for r in self._conn.execute(statement)]
