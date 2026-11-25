"""Contract tests for reader_cache_adapter (spec: planning/05-spec-fastreader-adaptation.md,
integration tests 3, 4 and 8), run through fastReader's own commands."""
import pytest

from planning_system.fastreader.cli import DEFAULT_CONFIG_PATH

from planning_system.contract import Invalid, NotFound
from planning_system.fastreader.commands.cite import run_cite
from planning_system.fastreader.commands.get import run_get
from planning_system.fastreader.commands.load import run_load_text
from planning_system.fastreader.commands.toc import run_toc
from planning_system.fastreader.scanner import load_config
from planning_system.server.domain.references.fakes import (FakeClock, FakeReferenceLibrary,
                                                            FakeTempCache,
                                                            InMemoryReferenceStorage,
                                                            InMemoryTempCacheStorage)
from planning_system.server.domain.references.reader_cache_adapter import ReaderCacheAdapter
from planning_system.server.domain.references.reader_cache_adapter_fakes import FakeReaderCacheAdapter

LEVEL7 = pytest.mark.xfail(strict=False, reason="level 7")
CONFIG = load_config(DEFAULT_CONFIG_PATH)
DOC = "# Title\n\n## Part one\nalpha\nbeta\n\n## Part two\ngamma\n"


class Env:
    def __init__(self, kind):
        self.kind = kind
        self.ref_storage = InMemoryReferenceStorage()
        self.library = FakeReferenceLibrary(self.ref_storage)
        self.temp_cache = FakeTempCache(InMemoryTempCacheStorage(), self.ref_storage, FakeClock())

    def adapter(self, agent_id="agent-1", is_admin=False):
        cls = FakeReaderCacheAdapter if self.kind == "fake" else ReaderCacheAdapter
        return cls(self.temp_cache, self.library, agent_id, is_admin, CONFIG)


@pytest.fixture(params=["fake", pytest.param("real", marks=LEVEL7)])
def env(request):
    return Env(request.param)


def _load(port, text=DOC, **info):
    return run_load_text(text, "doc.md", info, port, CONFIG)["cache_id"]


def test_load_then_toc_and_get_through_the_adapter(env):
    port = env.adapter()
    item_id = _load(port)
    assert run_toc(item_id, port, marker_types=["section"])
    assert "alpha" in run_get(item_id, port, section=1) or "gamma" in run_get(item_id, port, section=1)


def test_same_text_twice_gives_same_id(env):
    port = env.adapter()
    assert _load(port) == _load(port)


def test_load_reports_strategy(env):
    result = run_load_text(DOC, "doc.pdf", {"strategy_used": "pypdf_text",
                                            "available_strategies": ["pypdf_text", "ocr"]},
                           env.adapter(), CONFIG)
    assert result["strategy_used"] == "pypdf_text"
    assert result["available_strategies"] == ["pypdf_text", "ocr"]


def test_another_agents_id_is_not_found(env):
    item_id = _load(env.adapter("agent-1"))
    with pytest.raises(NotFound):
        run_get(item_id, env.adapter("agent-2"), section=1)


def test_admin_can_read_another_agents_item(env):
    item_id = _load(env.adapter("agent-1"))
    assert env.adapter("admin", is_admin=True).get(item_id).text == DOC


def test_unknown_id_not_found_propagates(env):
    with pytest.raises(NotFound):
        run_get("nope", env.adapter(), section=1)


def test_cite_moves_item_into_references_keeping_its_id(env):
    port = env.adapter()
    item_id = _load(port)
    citation = run_cite(port, item_id, 3, 5)
    assert (citation.item_id, citation.start_line, citation.end_line) == (item_id, 3, 5)
    assert env.library.get(item_id).text == DOC


def test_cite_past_the_end_is_invalid(env):
    port = env.adapter()
    item_id = _load(port)
    with pytest.raises((Invalid, ValueError)):
        run_cite(port, item_id, 3, 99)


def test_cite_refuses_web_search_results(env):
    port = env.adapter()
    item_id = _load(port, "result one\nresult two", origin_kind="web_search")
    with pytest.raises(Invalid):
        run_cite(port, item_id, 1, 1)


def test_a_reference_id_loads_with_a_scanned_manifest(env):
    ref = env.library.store_node_text(DOC, node_id=7)
    item = env.adapter().get(ref.id)
    assert item.text == DOC
    assert item.manifest.markers.get("section")
