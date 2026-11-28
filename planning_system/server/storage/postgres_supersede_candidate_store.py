"""postgres_supersede_candidate_store: implements references' SupersedeCandidateStoragePort. Declares
supersede_candidates (migration 0004)."""
from __future__ import annotations

from sqlalchemy import BigInteger, Column, DateTime, Index, Table, Text, select, update
from sqlalchemy.engine import Connection

from planning_system.server.domain.references import SupersedeCandidate, SupersedeCandidateStoragePort

from .metadata import METADATA

SUPERSEDE_CANDIDATES = Table(
    "supersede_candidates", METADATA,
    Column("id", Text, primary_key=True),
    Column("project_id", BigInteger, nullable=False),
    Column("old_reference_id", Text, nullable=False, index=True),
    Column("new_reference_id", Text, nullable=False, index=True),
    Column("kind", Text, nullable=False),
    Column("found_by", Text, nullable=False),
    Column("status", Text, nullable=False),
    Column("proposed_by", Text),
    Column("reason", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("decided_by", Text),
    Column("decided_at", DateTime(timezone=True)),
    Column("request_node_id", BigInteger),
    Index("ix_supersede_candidates_project_status", "project_id", "status"),
)

_FIELDS = ("id", "project_id", "old_reference_id", "new_reference_id", "kind", "found_by", "status", "proposed_by",
           "reason", "created_at", "decided_by", "decided_at", "request_node_id")
_ORDER = (SUPERSEDE_CANDIDATES.c.created_at, SUPERSEDE_CANDIDATES.c.id)


class PostgresSupersedeCandidateStore(SupersedeCandidateStoragePort):
    def __init__(self, conn: Connection):
        self._conn = conn

    def add(self, candidate):
        self._conn.execute(SUPERSEDE_CANDIDATES.insert().values(**_row(candidate)))

    def get(self, candidate_id):
        found = self._records(select(SUPERSEDE_CANDIDATES).where(SUPERSEDE_CANDIDATES.c.id == candidate_id))
        return found[0] if found else None

    def save(self, candidate):
        row = _row(candidate)
        self._conn.execute(update(SUPERSEDE_CANDIDATES).where(SUPERSEDE_CANDIDATES.c.id == candidate.id)
                           .values(**{k: v for k, v in row.items() if k != "id"}))

    def find(self, project_id=None, status=None, old_reference_id=None, new_reference_id=None):
        c = SUPERSEDE_CANDIDATES.c
        statement = select(SUPERSEDE_CANDIDATES)
        for column, value in ((c.project_id, project_id), (c.status, status), (c.old_reference_id, old_reference_id),
                              (c.new_reference_id, new_reference_id)):
            if value is not None:
                statement = statement.where(column == value)
        return self._records(statement.order_by(*_ORDER))

    def _records(self, statement):
        return [SupersedeCandidate(**{f: r._mapping[f] for f in _FIELDS}) for r in self._conn.execute(statement)]


def _row(candidate: SupersedeCandidate) -> dict:
    return {f: getattr(candidate, f) for f in _FIELDS}
