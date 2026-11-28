"""postgres_reference_store: implements references' ReferenceStoragePort. Declares `references`.
Text is never updated and nothing is deleted; only superseded_by changes."""
from __future__ import annotations

import re

from sqlalchemy import JSON, Column, Table, Text, func, literal_column
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Connection

from planning_system.server.domain.references import ReferenceStoragePort
from planning_system.server.domain.references import Reference

from .metadata import METADATA

SEARCHABLE_CHARACTERS = 200_000

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

    def find_by_locator(self, locator):
        c = REFERENCES.c
        rows = self._conn.execute(select(REFERENCES).where(c.metadata["locator"].as_string() == locator,
                                                           c.superseded_by.is_(None)).order_by(c.id))
        return [_reference(r) for r in rows]

    def search_text(self, terms, limit):
        """Postgres full-text (english), any term, ranked by ts_rank. The document side is capped at
        SEARCHABLE_CHARACTERS (a tsvector holds at most 1 MB); migration 0004 indexes the same expression."""
        words = [w for w in (re.sub(r"[^a-z0-9]", "", t.lower()) for t in terms) if w]
        if not words:
            return []
        query = func.to_tsquery("english", " | ".join(words))
        document = searchable_text(REFERENCES.c.text)
        rows = self._conn.execute(select(REFERENCES).where(document.op("@@")(query),
                                                           REFERENCES.c.superseded_by.is_(None))
                                  .order_by(func.ts_rank(document, query).desc(), REFERENCES.c.id).limit(limit))
        return [_reference(r) for r in rows]

    def _one(self, statement):
        r = self._conn.execute(statement).first()
        return None if r is None else _reference(r)


def _reference(r) -> Reference:
    return Reference(r.id, r.origin, r.text, r.sha256, dict(r.metadata), r.owner, r.superseded_by)


def searchable_text(text_column):
    return func.to_tsvector(literal_column("'english'::regconfig"), func.left(text_column, SEARCHABLE_CHARACTERS))
