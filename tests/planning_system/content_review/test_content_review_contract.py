"""Contract tests for content_review (spec tests 9-10), run against [fake, real]. The real ledger runs
over the in-memory storage port here; the Postgres store's SKIP LOCKED take runs on a throwaway
database (two connections) in test_review_store_postgres.py."""
from datetime import timedelta

import pytest

from planning_system.contract import Conflict, NotFound
from planning_system.server.domain.content_review import (FAILED, PASSED, PENDING, SUPERSEDED, TAKEN,
                                                          ReviewLedgerService, Verdict)
from planning_system.server.domain.content_review.fakes import (FakeReviewLedger, InMemoryReviewStorage,
                                                                TickingClock)
from planning_system.server.domain.project_tree.fakes import FakeProjectTree, InMemoryTreeStorage
from planning_system.server.domain.project_tree.fakes import TickingClock as TreeClock
from planning_system.server.domain.references.fakes import FakeReferenceLibrary, InMemoryReferenceStorage
from planning_system.server.domain.references.types import Reference


@pytest.fixture
def world():
    storage = InMemoryReferenceStorage()
    references = FakeReferenceLibrary(storage)
    tree = FakeProjectTree(InMemoryTreeStorage(), references, TreeClock())
    project = tree.create(None, "P", "what we're doing", "p")
    node = tree.create(project.id, "cache lifetime", "high-level plan", "How long entries live.")
    user = references.store_user_exchange("s-1", "Use 72 hours.", "How long should entries live?")
    storage.save(Reference("ref-doc", "document", "a\nTTL is 72 hours\nc", "sha-doc"))
    content = tree.add_content(node.id, f"TTL is 72 hours [{user.id}:2-2] [ref-doc:2-2]", ("requirement",))
    return dict(references=references, tree=tree, project=project, node=node, user=user, content=content)


@pytest.fixture(params=["fake", "real"])
def make_ledger(request, world):
    def make(clock=None):
        clock = clock or TickingClock()
        if request.param == "fake":
            return FakeReviewLedger(world["references"], world["tree"], clock)
        return ReviewLedgerService(InMemoryReviewStorage(), world["references"], world["tree"], clock)
    return make


def open_one(ledger, world):
    return ledger.open(world["project"].id, world["node"].id, world["content"].reference_id, "requirement")


# 9
def test_9_open_is_pending_and_listed(make_ledger, world):
    ledger = make_ledger()
    record = open_one(ledger, world)
    assert record.status == PENDING and record.id.startswith("rev-") and record.reviewer is None
    assert [r.id for r in ledger.list(world["project"].id, PENDING)] == [record.id]
    assert ledger.list(world["project"].id, FAILED) == []
    assert ledger.list(world["project"].id, node_id=world["node"].id)[0].id == record.id
    assert ledger.get(record.id) == record
    with pytest.raises(NotFound):
        ledger.get("rev-missing")


def test_9b_take_marks_taken_and_never_hands_out_the_same_record_twice(make_ledger, world):
    ledger = make_ledger()
    first, second = open_one(ledger, world), open_one(ledger, world)
    a = ledger.take_next(world["project"].id, "reviewer-a")
    b = ledger.take_next(world["project"].id, "reviewer-b")
    assert {a.review_id, b.review_id} == {first.id, second.id}
    assert a.review_id == first.id                              # oldest first
    assert ledger.take_next(world["project"].id, "reviewer-c") is None
    assert ledger.get(first.id).status == TAKEN and ledger.get(first.id).reviewer == "reviewer-a"


def test_9c_only_the_holder_submits_or_releases(make_ledger, world):
    ledger = make_ledger()
    record = open_one(ledger, world)
    with pytest.raises(Conflict):
        ledger.submit(record.id, "reviewer-a", Verdict(True, "ok"))        # not taken yet
    ledger.take_next(world["project"].id, "reviewer-a")
    with pytest.raises(Conflict):
        ledger.submit(record.id, "intruder", Verdict(True, "ok"))
    with pytest.raises(Conflict):
        ledger.release(record.id, "intruder")
    decided = ledger.submit(record.id, "reviewer-a", Verdict(False, "quote does not say 72", "cache lifetime"))
    assert (decided.status, decided.reason, decided.suggested_title) == (FAILED, "quote does not say 72",
                                                                         "cache lifetime")
    assert decided.decided_at is not None
    with pytest.raises(Conflict):
        ledger.submit(record.id, "reviewer-a", Verdict(True, "again"))


def test_9d_release_returns_to_pending(make_ledger, world):
    ledger = make_ledger()
    record = open_one(ledger, world)
    ledger.take_next(world["project"].id, "reviewer-a")
    ledger.release(record.id, "reviewer-a")
    assert ledger.get(record.id).status == PENDING and ledger.get(record.id).reviewer is None
    assert ledger.take_next(world["project"].id, "reviewer-b").review_id == record.id


def test_9e_lease_expiry_returns_a_taken_record_to_pending(make_ledger, world):
    clock = TickingClock()
    ledger = make_ledger(clock)
    record = open_one(ledger, world)
    ledger.take_next(world["project"].id, "reviewer-a")
    assert ledger.expire_leases(timedelta(minutes=10)) == 0
    clock.advance(timedelta(minutes=11))
    assert ledger.take_next(world["project"].id, "reviewer-b").review_id == record.id   # expired at take
    assert ledger.get(record.id).reviewer == "reviewer-b"


def test_9f_supersede_for_marks_the_content_items_records_superseded(make_ledger, world):
    ledger = make_ledger()
    record = open_one(ledger, world)
    ledger.take_next(world["project"].id, "reviewer-a")
    ledger.submit(record.id, "reviewer-a", Verdict(False, "no"))
    pending = open_one(ledger, world)
    ledger.supersede_for(world["content"].reference_id)
    assert {ledger.get(record.id).status, ledger.get(pending.id).status} == {SUPERSEDED}
    assert ledger.blocking_for_node(world["node"].id) == []


def test_9g_blocking_for_node_is_pending_taken_and_failed(make_ledger, world):
    ledger = make_ledger()
    record = open_one(ledger, world)
    assert [r.id for r in ledger.blocking_for_node(world["node"].id)] == [record.id]
    ledger.take_next(world["project"].id, "a")
    assert len(ledger.blocking_for_node(world["node"].id)) == 1
    ledger.submit(record.id, "a", Verdict(False, "no"))
    assert len(ledger.blocking_for_node(world["node"].id)) == 1
    other = open_one(ledger, world)
    ledger.take_next(world["project"].id, "a")
    ledger.submit(other.id, "a", Verdict(True, "ok"))
    assert [r.id for r in ledger.blocking_for_node(world["node"].id)] == [record.id]
    assert ledger.get(other.id).status == PASSED


# 10
def test_10_packet_inlines_the_quotes(make_ledger, world):
    ledger = make_ledger()
    record = open_one(ledger, world)
    packet = ledger.take_next(world["project"].id, "reviewer-a")
    assert packet.review_id == record.id
    assert (packet.node_title, packet.node_context_summary) == ("cache lifetime", "How long entries live.")
    assert packet.claim_tag == "requirement" and packet.claim_text.startswith("TTL is 72 hours")
    user, doc = packet.citations
    assert (user.origin, user.quoted_text) == ("user_exchange", "Use 72 hours.")
    assert user.pre_text == "How long should entries live?"
    assert user.full_text == "How long should entries live?\nUse 72 hours."
    assert (doc.origin, doc.quoted_text, doc.pre_text, doc.full_text) == ("document", "TTL is 72 hours", "", "")
