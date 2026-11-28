"""Supersede candidates (05-spec-reference-supersede.md, approved): never automatic; confirm supersedes; reject
keeps the pair with its reason. Run against [fake, real]."""
import pytest

from planning_system.contract import Conflict, Invalid, NotFound
from planning_system.server.domain.references import SupersedeCandidateRegistry
from planning_system.server.domain.references.fakes import (FakeClock, FakeReferenceLibrary, FakeSupersedeCandidates,
                                                            InMemoryReferenceStorage,
                                                            InMemorySupersedeCandidateStorage)
from planning_system.server.domain.references.types import Reference


@pytest.fixture
def library():
    storage = InMemoryReferenceStorage()
    for ref_id, origin in [("doc-old", "document"), ("doc-new", "document"), ("kb", "knowledge_base"),
                           ("q-old", "user_exchange"), ("q-new", "user_exchange"), ("reply", "proposal_response"),
                           ("node", "node")]:
        storage.save(Reference(ref_id, origin, f"text of {ref_id}", f"sha-{ref_id}"))
    return FakeReferenceLibrary(storage)


@pytest.fixture(params=["fake", "real"])
def candidates(request, library):
    if request.param == "fake":
        return FakeSupersedeCandidates(library, FakeClock())
    return SupersedeCandidateRegistry(InMemorySupersedeCandidateStorage(), library, FakeClock())


def test_propose_is_a_record_and_supersedes_nothing(candidates, library):
    candidate, created = candidates.propose(1, "doc-old", "doc-new", "same_source", None, "reloaded")
    assert created and candidate.id.startswith("sup-")
    assert (candidate.status, candidate.kind, candidate.found_by, candidate.reason) == \
        ("proposed", "document", "same_source", "reloaded")
    assert library.get("doc-old", follow_superseded=False).superseded_by is None
    assert candidates.get(candidate.id) == candidate
    assert [c.id for c in candidates.list(1)] == [candidate.id] and candidates.list(2) == []
    with pytest.raises(NotFound):
        candidates.get("sup-missing")


def test_same_pair_returns_the_existing_record(candidates):
    first, _ = candidates.propose(1, "q-old", "q-new", "quote_check", None)
    again, created = candidates.propose(1, "q-old", "q-new", "proposed", "planner-1")
    assert (again.id, created, again.kind) == (first.id, False, "user_quote")


@pytest.mark.parametrize("old, new", [("doc-old", "doc-old"), ("doc-old", "q-new"), ("q-old", "kb"),
                                      ("node", "doc-new"), ("doc-old", "missing")])
def test_bad_pairs_are_rejected(candidates, old, new):
    with pytest.raises((Invalid, NotFound)):
        candidates.propose(1, old, new, "proposed", "planner-1")


def test_document_and_knowledge_base_mix_and_user_quote_and_reply_mix(candidates):
    assert candidates.propose(1, "doc-old", "kb", "proposed", "p")[0].kind == "document"
    assert candidates.propose(1, "q-old", "reply", "proposed", "p")[0].kind == "user_quote"


def test_confirm_supersedes_and_reject_keeps_the_reason(candidates, library):
    confirmed, _ = candidates.propose(1, "doc-old", "doc-new", "same_source", None)
    rejected, _ = candidates.propose(1, "q-old", "q-new", "quote_check", None)
    candidates.mark_trial_reviewed(confirmed.id, 42)
    assert candidates.get(confirmed.id).request_node_id == 42
    done = candidates.confirm(confirmed.id, "planner-1")
    assert (done.status, done.decided_by) == ("confirmed", "planner-1") and done.decided_at is not None
    assert library.get("doc-old", follow_superseded=False).superseded_by == "doc-new"
    kept = candidates.reject(rejected.id, "admin", "the user only clarified")
    assert (kept.status, kept.reason) == ("rejected", "the user only clarified")
    assert library.get("q-old", follow_superseded=False).superseded_by is None
    for decided in (confirmed.id, rejected.id):
        with pytest.raises(Conflict):
            candidates.confirm(decided, "admin")
        with pytest.raises(Conflict):
            candidates.reject(decided, "admin", "again")
    assert candidates.propose(1, "q-old", "q-new", "quote_check", None)[0].status == "rejected"
    assert [c.status for c in candidates.list(1, "rejected")] == ["rejected"]
    with pytest.raises(Invalid):
        candidates.propose(2, "doc-old", "doc-new", "proposed", "p")          # old is superseded now
