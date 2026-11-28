"""related_reference_finder (05-spec-reference-supersede.md "Search first"): stored references from the same
source (URL or file name) and the top same-topic matches (full-text; Postgres in the real store, simple word
matching in the fake). Contract run against [fake, real] finders over the in-memory storage; the Postgres
store's two lookups are tested in tests/planning_system/storage/test_storage_contract.py."""
import pytest

from planning_system.server.domain.references import RelatedReferenceFinder
from planning_system.server.domain.references.fakes import FakeRelatedReferences, InMemoryReferenceStorage
from planning_system.server.domain.references.types import Reference


@pytest.fixture
def storage():
    s = InMemoryReferenceStorage()
    s.save(Reference("ref-old", "document", "Caching guide\nEntries expire after seventy two hours.\n", "sha-1",
                     {"locator": "https://x/cache"}))
    s.save(Reference("ref-gone", "document", "Caching guide\nold old\n", "sha-0", {"locator": "https://x/cache"},
                     superseded_by="ref-old"))
    s.save(Reference("ref-other", "document", "Queue guide\nMessages are retried twice.\n", "sha-2",
                     {"locator": "https://x/queue"}))
    s.save(Reference("ref-user", "user_exchange", "How long?\nCache entries should expire after 72 hours.", "sha-3"))
    s.save(Reference("ref-node", "node", "Messages are retried twice [ref-other:2-2]", "sha-4"))   # never listed
    return s


@pytest.fixture(params=["fake", "real"])
def finder(request, storage):
    return FakeRelatedReferences(storage) if request.param == "fake" else RelatedReferenceFinder(storage)


def test_same_source_lists_current_references_with_that_locator(finder):
    found = finder.related("https://x/cache", "Caching guide\nEntries now expire after one day.", exclude_id="ref-new")
    assert [r.id for r in found.same_source] == ["ref-old"]
    assert found.same_source[0].locator == "https://x/cache" and found.same_source[0].preview == "Caching guide"


def test_same_topic_ranks_matching_text_and_skips_the_same_source_and_itself(finder):
    found = finder.related(None, "How long do cache entries live before they expire?", exclude_id="ref-user")
    ids = [r.id for r in found.same_topic]
    assert ids and ids[0] == "ref-old" and "ref-user" not in ids and "ref-gone" not in ids
    assert "ref-other" not in ids


def test_search_finds_stored_references_by_words(finder):
    assert [r.id for r in finder.search("retried messages")] == ["ref-other"]
    assert finder.search("zebra") == []
    assert finder.search("   ") == []
