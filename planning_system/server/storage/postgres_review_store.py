"""postgres_review_store: implements content_review's ReviewStoragePort. Declares content_reviews.
lock_oldest_pending is SELECT ... FOR UPDATE SKIP LOCKED LIMIT 1 so two reviewers never get one record."""
from __future__ import annotations

from sqlalchemy import BigInteger, Column, DateTime, Index, Table, Text, select, update
from sqlalchemy.engine import Connection

from planning_system.server.domain.content_review.ports import ReviewStoragePort
from planning_system.server.domain.content_review.types import PENDING, TAKEN, ReviewRecord

from .metadata import METADATA

CONTENT_REVIEWS = Table(
    "content_reviews", METADATA,
    Column("id", Text, primary_key=True),
    Column("project_id", BigInteger, nullable=False),
    Column("node_id", BigInteger, nullable=False, index=True),
    Column("content_reference_id", Text, nullable=False, index=True),
    Column("claim_tag", Text, nullable=False),
    Column("status", Text, nullable=False),
    Column("reviewer", Text),
    Column("taken_at", DateTime(timezone=True)),
    Column("reason", Text, nullable=False),
    Column("suggested_title", Text),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("decided_at", DateTime(timezone=True)),
    Index("ix_content_reviews_project_status", "project_id", "status"),
)

_FIELDS = ("id", "project_id", "node_id", "content_reference_id", "claim_tag", "status", "reviewer", "taken_at",
           "reason", "suggested_title", "created_at", "decided_at")
_ORDER = (CONTENT_REVIEWS.c.created_at, CONTENT_REVIEWS.c.id)


class PostgresReviewStore(ReviewStoragePort):
    def __init__(self, conn: Connection):
        self._conn = conn

    def add(self, record):
        self._conn.execute(CONTENT_REVIEWS.insert().values(**_row(record)))

    def get(self, review_id):
        found = self._records(select(CONTENT_REVIEWS).where(CONTENT_REVIEWS.c.id == review_id))
        return found[0] if found else None

    def save(self, record):
        row = _row(record)
        self._conn.execute(update(CONTENT_REVIEWS).where(CONTENT_REVIEWS.c.id == record.id)
                           .values(**{k: v for k, v in row.items() if k != "id"}))

    def find(self, project_id=None, statuses=None, node_id=None, content_reference_id=None):
        c = CONTENT_REVIEWS.c
        statement = select(CONTENT_REVIEWS)
        if project_id is not None:
            statement = statement.where(c.project_id == project_id)
        if statuses is not None:
            statement = statement.where(c.status.in_(list(statuses)))
        if node_id is not None:
            statement = statement.where(c.node_id == node_id)
        if content_reference_id is not None:
            statement = statement.where(c.content_reference_id == content_reference_id)
        return self._records(statement.order_by(*_ORDER))

    def lock_oldest_pending(self, project_id):
        c = CONTENT_REVIEWS.c
        statement = (select(CONTENT_REVIEWS).where(c.project_id == project_id, c.status == PENDING)
                     .order_by(*_ORDER).limit(1).with_for_update(skip_locked=True))
        found = self._records(statement)
        return found[0] if found else None

    def taken_before(self, cutoff):
        c = CONTENT_REVIEWS.c
        return self._records(select(CONTENT_REVIEWS).where(c.status == TAKEN, c.taken_at < cutoff)
                             .order_by(*_ORDER))

    def _records(self, statement):
        return [ReviewRecord(**{f: r._mapping[f] for f in _FIELDS}) for r in self._conn.execute(statement)]


def _row(record: ReviewRecord) -> dict:
    return {f: getattr(record, f) for f in _FIELDS}
