"""postgres_reference_store: implements references' ReferenceStoragePort. Declares `references`.
Text is never updated and nothing is deleted; only superseded_by changes."""
from __future__ import annotations

from sqlalchemy import JSON, Column, Table, Text
from sqlalchemy.engine import Connection

from planning_system.server.domain.references.ports import ReferenceStoragePort

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
        raise NotImplementedError("level 7")

    def find_by_sha256(self, sha256):
        raise NotImplementedError("level 7")

    def save(self, reference):
        raise NotImplementedError("level 7")   # insert; on an existing id only superseded_by may change
