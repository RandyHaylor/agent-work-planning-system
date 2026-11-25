"""postgres_reference_store: implements references' ReferenceStoragePort. Declares `references`.
Text is never updated and nothing is deleted; only superseded_by changes."""
from __future__ import annotations

from sqlalchemy import JSON, Column, Table, Text
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Connection

from planning_system.server.domain.references.ports import ReferenceStoragePort
from planning_system.server.domain.references.types import Reference

from .metadata import METADATA

REFERENCES = Table(
    "references", METADATA,
    Column("id", Text, primary_key=True),
    Column("origin", Text, nullable=False),
    Column("text", Text, nullable=False),
    Column("sha256", Text, nullable=False, index=True),
    Column("metadata", JSON, nullable=False),
    Column("owner", Text, nullable=True),
    Column("superseded_by", Text, nullable=True),
)


class PostgresReferenceStore(ReferenceStoragePort):
    def __init__(self, conn: Connection):
        self._conn = conn

    def get(self, ref_id):
        return self._one(select(REFERENCES).where(REFERENCES.c.id == ref_id))

    def find_by_sha256(self, sha256):
        # prefer a current (not superseded) reference when several share the text
        return self._one(select(REFERENCES).where(REFERENCES.c.sha256 == sha256)
                         .order_by(REFERENCES.c.superseded_by.is_not(None), REFERENCES.c.id).limit(1))

    def save(self, reference):
        """Insert; on an existing id only superseded_by changes (text is never updated)."""
        statement = insert(REFERENCES).values(
            id=reference.id, origin=reference.origin, text=reference.text, sha256=reference.sha256,
            metadata=dict(reference.metadata), owner=reference.owner, superseded_by=reference.superseded_by)
        self._conn.execute(statement.on_conflict_do_update(
            index_elements=[REFERENCES.c.id], set_={"superseded_by": statement.excluded.superseded_by}))

    def _one(self, statement):
        r = self._conn.execute(statement).first()
        if r is None:
            return None
        return Reference(r.id, r.origin, r.text, r.sha256, dict(r.metadata), r.owner, r.superseded_by)
