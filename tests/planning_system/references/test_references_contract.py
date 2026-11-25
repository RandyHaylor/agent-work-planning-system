"""Contract tests for references: ReferenceLibrary + temp cache (spec: planning/05-spec-references-and-reader.md).

The spec has no numbered test list; these test the behaviour it states in sections 3 and 4.
"""
from datetime import timedelta

import pytest

from planning_system.contract import Invalid, NotFound
from planning_system.server.domain.references.fakes import (FakeClock, FakeReferenceLibrary,
                                                            FakeTempCache,
                                                            InMemoryReferenceStorage,
                                                            InMemoryTempCacheStorage)
from planning_system.server.domain.references.reference_library import ReferenceLibraryService
from planning_system.server.domain.references.temp_cache_lifecycle import TempCacheLifecycle
from planning_system.server.domain.references.types import Citation

LEVEL7 = pytest.mark.xfail(strict=False, reason="level 7")
TTL = timedelta(days=1)
DOC = "line one\nline two\nline three\nline four"


class Env:
    def __init__(self, kind):
        self.ref_storage = InMemoryReferenceStorage()
        self.temp_storage = InMemoryTempCacheStorage()
        self.clock = FakeClock()
        if kind == "fake":
            self.library = FakeReferenceLibrary(self.ref_storage)
            self.cache = FakeTempCache(self.temp_storage, self.ref_storage, self.clock, TTL)
        else:
            self.library = ReferenceLibraryService(self.ref_storage)
            self.cache = TempCacheLifecycle(self.temp_storage, self.ref_storage, self.clock, TTL)


@pytest.fixture(params=["fake", pytest.param("real", marks=LEVEL7)])
def env(request):
    return Env(request.param)


def test_cite_moves_item_into_references_keeping_its_id(env):
    entry = env.cache.put("agent-1", DOC, {"url": "https://example.com"})
    citation = env.cache.cite(entry.cache_id, 2, 3)
    assert citation == Citation(entry.cache_id, 2, 3)
    ref = env.library.get(entry.cache_id)
    assert ref.text == DOC and ref.sha256 == entry.sha256 and ref.owner == "agent-1"
    assert env.library.render(citation) == "line two\nline three"


def test_cite_rejects_a_bad_line_range(env):
    entry = env.cache.put("agent-1", DOC, {})
    with pytest.raises(Invalid):
        env.cache.cite(entry.cache_id, 3, 9)


def test_identical_content_reuses_the_stored_copy(env):
    first = env.cache.cite(env.cache.put("agent-1", DOC, {}).cache_id, 1, 1)
    second = env.cache.cite(env.cache.put("agent-2", DOC, {}).cache_id, 1, 2)
    assert first.reference_id == second.reference_id
    a = env.library.store_user_exchange("s1", "do it like this", "agent said")
    b = env.library.store_user_exchange("s1", "do it like this", "agent said")
    assert a.id == b.id and a.origin == "user_exchange"


def test_read_lines_and_render(env):
    ref = env.library.store_node_text(DOC, node_id=5)
    assert env.library.read_lines(ref.id, 1, 2) == "line one\nline two"
    assert env.library.render(Citation(ref.id, 4, 4)) == "line four"
    with pytest.raises(Invalid):
        env.library.render(Citation(ref.id, 0, 2))


def test_store_node_text_with_replaces_supersedes(env):
    old = env.library.store_node_text("v1", node_id=5)
    new = env.library.store_node_text("v2", node_id=5, replaces=old.id)
    assert env.library.get(old.id, follow_superseded=False).superseded_by == new.id
    assert env.library.get(old.id).id == new.id
    assert env.library.get(old.id, follow_superseded=False).text == "v1"


def test_supersede_follows_a_chain(env):
    a = env.library.store_proposal_response(7, "a")
    b = env.library.store_proposal_response(7, "b")
    c = env.library.store_proposal_response(7, "c")
    env.library.supersede(a.id, b.id)
    env.library.supersede(b.id, c.id)
    assert env.library.get(a.id).text == "c"


def test_unknown_reference_is_not_found(env):
    with pytest.raises(NotFound):
        env.library.get("nope")


def test_temp_cache_ttl_purge(env):
    old = env.cache.put("agent-1", "old text", {})
    env.clock.advance(TTL + timedelta(seconds=1))
    fresh = env.cache.put("agent-1", "fresh text", {})
    assert env.cache.purge_expired() == 1
    with pytest.raises(NotFound):
        env.cache.get(old.cache_id)
    assert env.cache.get(fresh.cache_id).text == "fresh text"
