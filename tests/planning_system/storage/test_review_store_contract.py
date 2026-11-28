"""ReviewStoragePort contract [in-memory fake, Postgres], and spec test 9's concurrency case on real
Postgres: two connections taking at once never get the same record (SKIP LOCKED)."""
import secrets
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete

from planning_system.server.domain.content_review.fakes import InMemoryReviewStorage, TickingClock
from planning_system.server.domain.content_review.ports import ReviewStoragePort
from planning_system.server.domain.content_review.review_ledger import ReviewLedgerService
from planning_system.server.domain.content_review.types import FAILED, PENDING, TAKEN, ReviewRecord
from planning_system.server.storage import PostgresReviewStore
from planning_system.server.storage.postgres_review_store import CONTENT_REVIEWS

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def record(id, project_id=1, node_id=10, status=PENDING, created=0, **kw):
    base = dict(id=id, project_id=project_id, node_id=node_id, content_reference_id=f"ref-{id}",
                claim_tag="requirement", status=status, reviewer=None, taken_at=None, reason="",
                suggested_title=None, created_at=T0 + timedelta(seconds=created), decided_at=None)
    base.update(kw)
    return ReviewRecord(**base)


@pytest.fixture(params=["fake", "real"])
def review_store(request):
    if request.param == "fake":
        return InMemoryReviewStorage()
    return PostgresReviewStore(request.getfixturevalue("connection"))


def test_store_implements_the_port():
    assert issubclass(PostgresReviewStore, ReviewStoragePort)


def test_round_trip_save_and_find(review_store):
    review_store.add(record("rev-2", created=2))
    review_store.add(record("rev-1", created=1, node_id=11))
    review_store.add(record("rev-3", project_id=2, status=FAILED))
    assert review_store.get("rev-1") == record("rev-1", created=1, node_id=11)
    assert review_store.get("rev-x") is None
    assert [r.id for r in review_store.find(project_id=1)] == ["rev-1", "rev-2"]
    assert [r.id for r in review_store.find(statuses=[FAILED])] == ["rev-3"]
    assert [r.id for r in review_store.find(node_id=11)] == ["rev-1"]
    assert [r.id for r in review_store.find(content_reference_id="ref-rev-2")] == ["rev-2"]
    taken = record("rev-2", created=2, status=TAKEN, reviewer="a", taken_at=T0)
    review_store.save(taken)
    assert review_store.get("rev-2") == taken
    assert review_store.lock_oldest_pending(1).id == "rev-1"
    assert [r.id for r in review_store.taken_before(T0 + timedelta(seconds=1))] == ["rev-2"]
    assert review_store.taken_before(T0) == []


def test_node_review_round_trip(review_store):
    """Migration 0003: target_kind, and no content item for a node review."""
    node_review = record("rev-n", content_reference_id=None, claim_tag="", target_kind="node")
    review_store.add(node_review)
    review_store.add(record("rev-c"))
    assert review_store.get("rev-n") == node_review
    assert review_store.get("rev-c").target_kind == "content"
    assert [r.id for r in review_store.find(target_kind="node")] == ["rev-n"]


def test_trial_and_quote_check_round_trip(review_store):
    """Migration 0004: against_reference_id, candidate_id, findings."""
    trial = record("rev-t", target_kind="trial", against_reference_id="ref-new", candidate_id="sup-1")
    check = record("rev-q", target_kind="quote_check", against_reference_id="ref-q", findings=("ref-a", "ref-b"))
    review_store.add(trial)
    review_store.add(check)
    assert review_store.get("rev-t") == trial and review_store.get("rev-q") == check
    assert [r.id for r in review_store.find(candidate_id="sup-1")] == ["rev-t"]


def test_two_connections_never_take_the_same_record(engine):
    project = secrets.randbits(40)
    with engine.begin() as conn:
        store = PostgresReviewStore(conn)
        store.add(record(f"rev-a-{project}", project_id=project, created=1))
        store.add(record(f"rev-b-{project}", project_id=project, created=2))
    try:
        with engine.connect() as first, engine.connect() as second, engine.connect() as third:
            t1, t2, t3 = first.begin(), second.begin(), third.begin()
            a = PostgresReviewStore(first).lock_oldest_pending(project)
            b = PostgresReviewStore(second).lock_oldest_pending(project)
            assert a is not None and b is not None and a.id != b.id
            assert PostgresReviewStore(third).lock_oldest_pending(project) is None
            t1.rollback()
            t2.rollback()
            t3.rollback()
    finally:
        with engine.begin() as conn:
            conn.execute(delete(CONTENT_REVIEWS).where(CONTENT_REVIEWS.c.project_id == project))


def test_two_ledgers_on_two_connections_take_different_records(engine):
    """The real ledger end to end on Postgres: concurrent take_next in two open transactions."""
    project = secrets.randbits(40)
    with engine.begin() as conn:
        store = PostgresReviewStore(conn)
        for name, created in (("x", 1), ("y", 2)):
            store.add(record(f"rev-{name}-{project}", project_id=project, created=created,
                             content_reference_id="ref-none"))

    class NoQuotes:                                   # packet building reads these
        def get(self, ref_id, follow_superseded=True):
            from planning_system.server.domain.references.types import Reference
            return Reference(ref_id, "node", "no citations", "sha")

    class Tree:
        def get(self, node_id):
            from types import SimpleNamespace
            return SimpleNamespace(title="t", context_summary="c")

    try:
        with engine.connect() as first, engine.connect() as second:
            t1, t2 = first.begin(), second.begin()
            a = ReviewLedgerService(PostgresReviewStore(first), NoQuotes(), Tree(), TickingClock()).take_next(
                project, "a")
            b = ReviewLedgerService(PostgresReviewStore(second), NoQuotes(), Tree(), TickingClock()).take_next(
                project, "b")
            assert a.review_id != b.review_id
            t1.commit()
            t2.commit()
        with engine.connect() as conn:
            taken = PostgresReviewStore(conn).find(project_id=project)
            assert {(r.status, r.reviewer) for r in taken} == {(TAKEN, "a"), (TAKEN, "b")}
    finally:
        with engine.begin() as conn:
            conn.execute(delete(CONTENT_REVIEWS).where(CONTENT_REVIEWS.c.project_id == project))
