"""Contract tests for context_assembly (spec: planning/05-spec-context-assembly.md); the tree is the
project_tree fake (mocked ProjectTree) over the references fake."""
import pytest

from planning_system.server.domain.context_assembly.context_assembler import ContextAssemblerService
from planning_system.server.domain.context_assembly.fakes import FakeContextAssembler
from planning_system.server.domain.project_tree.fakes import (FakeProjectTree, InMemoryTreeStorage,
                                                              TickingClock)
from planning_system.server.domain.references.fakes import FakeReferenceLibrary

@pytest.fixture(params=["fake", "real"])
def env(request):
    refs = FakeReferenceLibrary()
    tree = FakeProjectTree(InMemoryTreeStorage(), refs, TickingClock())
    cls = FakeContextAssembler if request.param == "fake" else ContextAssemblerService
    project = tree.create(None, "p", "what we're doing", "SUMMARY-1")
    l2 = tree.create(project.id, "d", "definition of done", "SUMMARY-2")
    tree.add_content(l2.id, "ANCESTOR-REQUIREMENT", ("requirement",))
    l3 = tree.create(l2.id, "h", "high-level plan", "SUMMARY-3")
    task = tree.create(l3.id, "t", "walkthroughs", "SUMMARY-TASK")
    tree.add_content(task.id, "OWN-CONTENT-A", ())
    tree.add_content(task.id, "OWN-CONTENT-B", ())
    return cls(tree, refs), tree, (project, l2, l3, task)


def test_1_ancestor_summaries_root_first_then_own_content(env):
    assembler, _, (project, l2, l3, task) = env
    ctx = assembler.assemble(task.id)
    order = ["SUMMARY-1", "SUMMARY-2", "SUMMARY-3", "OWN-CONTENT-A", "OWN-CONTENT-B"]
    positions = [ctx.text.index(s) for s in order]
    assert positions == sorted(positions)
    assert ctx.node_id == task.id
    assert ctx.sources == (project.id, l2.id, l3.id, task.id)


def test_2_ancestor_content_not_included(env):
    assembler, _, (*_, task) = env
    assert "ANCESTOR-REQUIREMENT" not in assembler.assemble(task.id).text


def test_3_abandoned_ancestors_left_out(env):
    assembler, tree, (project, l2, l3, task) = env
    tree.set_state(l3.id, "abandoned")
    ctx = assembler.assemble(task.id)
    assert "SUMMARY-3" not in ctx.text
    assert l3.id not in ctx.sources


def test_4_changed_summary_shows_next_time(env):
    assembler, tree, (project, l2, l3, task) = env
    assembler.assemble(task.id)
    tree.update(l2.id, context_summary="SUMMARY-2-CHANGED")
    text = assembler.assemble(task.id).text
    assert "SUMMARY-2-CHANGED" in text
