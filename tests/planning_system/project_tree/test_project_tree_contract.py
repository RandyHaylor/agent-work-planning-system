"""Contract tests for project_tree (spec: planning/05-spec-project-tree.md); mocked storage and
ReferenceLibrary (the references fake); permission rule through the access fake."""
import pytest

from planning_system.contract import Invalid, Principal
from planning_system.server.domain.access.fakes import TablePermissionPolicy
from planning_system.server.domain.access.types import NodeFacts
from planning_system.server.domain.project_tree.fakes import (FakeProjectTree, InMemoryTreeStorage,
                                                              TickingClock)
from planning_system.server.domain.project_tree.interface import ProjectTree
from planning_system.server.domain.project_tree.ports import TreeStoragePort
from planning_system.server.domain.project_tree.project_tree import ProjectTreeService
from planning_system.server.domain.references.fakes import FakeReferenceLibrary

SPIKE = ("tech spike",)


@pytest.fixture(params=["fake", "real"])
def env(request):
    refs = FakeReferenceLibrary()
    cls = FakeProjectTree if request.param == "fake" else ProjectTreeService
    return cls(InMemoryTreeStorage(), refs, TickingClock()), refs


@pytest.fixture
def tree(env):
    return env[0]


def chain_to_level_4(tree):
    project = tree.create(None, "project", "what we're doing", "build X")
    l2 = tree.create(project.id, "done means", "definition of done", "s2")
    l3 = tree.create(l2.id, "plan", "high-level plan", "s3")
    l4 = tree.create(l3.id, "walkthroughs", "walkthroughs", "s4")
    return project, l2, l3, l4


def siblings(tree, n, **deps):
    parent = chain_to_level_4(tree)[3]
    return parent, [tree.create(parent.id, f"t{i}", "build", f"s{i}", depends_on=deps.get(f"t{i}"))
                    for i in range(1, n + 1)]


def test_1_levels_1_to_4_take_one_main_child_supplementary_exempt_level_5_branches(tree):
    project, l2, l3, l4 = chain_to_level_4(tree)
    for parent in (project, l2, l3):
        with pytest.raises(Invalid):
            tree.create(parent.id, "second", "x", "s")
        assert tree.create(parent.id, "spike", "x", "s", labels=SPIKE).labels == frozenset(SPIKE)
        tree.create(parent.id, "ask", "x", "s", labels=("requirement request",))
    for i in range(3):
        tree.create(l4.id, f"module {i}", "module specs", "s")
    assert len(tree.children(l4.id)) == 3


def test_2_children_in_position_order_and_move_renumbers(tree):
    parent, (a, b, c) = siblings(tree, 3)
    assert [n.id for n in tree.children(parent.id)] == [a.id, b.id, c.id]
    first = tree.create(parent.id, "first", "build", "s", position=0)
    assert [n.id for n in tree.children(parent.id)] == [first.id, a.id, b.id, c.id]
    tree.move(c.id, parent.id, 1)
    kids = tree.children(parent.id)
    assert [n.id for n in kids] == [first.id, c.id, a.id, b.id]
    assert [n.position for n in kids] == [0, 1, 2, 3]
    other = tree.create(parent.id, "other parent", "build", "s")
    tree.move(a.id, other.id, 0)
    assert [n.position for n in tree.children(parent.id)] == [0, 1, 2, 3]
    assert tree.get(a.id).parent_id == other.id


def test_3_no_depends_on_means_previous_sibling(tree):
    parent, (t1, t2, t3) = siblings(tree, 3)
    assert t2.depends_on is None
    assert [n.id for n in tree.ready_siblings(parent.id)] == [t1.id]
    tree.set_state(t1.id, "done")
    assert [n.id for n in tree.ready_siblings(parent.id)] == [t2.id]


def test_4_explicit_dependencies_allow_parallel(tree):
    parent = chain_to_level_4(tree)[3]
    t1 = tree.create(parent.id, "t1", "build", "s")
    t2 = tree.create(parent.id, "t2", "build", "s")
    t3 = tree.create(parent.id, "t3", "build", "s", depends_on=(t1.id,))
    t4 = tree.create(parent.id, "t4", "build", "s", depends_on=(t1.id,))
    tree.set_state(t1.id, "done")
    assert {n.id for n in tree.ready_siblings(parent.id)} == {t2.id, t3.id, t4.id}


@pytest.mark.parametrize("explicit", [False, True])
def test_5_insert_before_places_and_adds_dependency(tree, explicit):
    parent = chain_to_level_4(tree)[3]
    t1 = tree.create(parent.id, "t1", "build", "s")
    t2 = tree.create(parent.id, "t2", "build", "s", depends_on=(t1.id,) if explicit else None)
    spike = tree.insert_before(t2.id, "spike", SPIKE, "find out")
    kids = tree.children(parent.id)
    assert [n.id for n in kids] == [t1.id, spike.id, t2.id]
    assert spike.id in tree.get(t2.id).depends_on
    assert t1.id in tree.get(t2.id).depends_on


def test_6_abandoned_skipped_in_dependencies_and_never_ready(tree):
    parent, (t1, t2, t3) = siblings(tree, 3)
    tree.set_state(t1.id, "abandoned")
    ready = [n.id for n in tree.ready_siblings(parent.id)]
    assert ready == [t2.id]
    assert t1.id not in ready


def test_7_no_delete_abandoned_stays_readable(env):
    tree, refs = env
    parent, (t1,) = siblings(tree, 1)
    content = tree.add_content(t1.id, "the text", ("note",))
    tree.set_state(t1.id, "abandoned")
    assert tree.get(t1.id).state == "abandoned"
    assert tree.content(t1.id) == [content]
    assert refs.get(content.reference_id).text == "the text"
    for name in ("delete", "remove"):
        assert not hasattr(ProjectTree, name)
        assert not hasattr(TreeStoragePort, name)


def test_8_every_change_moves_last_verified(tree):
    parent, (t1, t2) = siblings(tree, 2)
    before = tree.get(t1.id).last_verified
    updated = tree.update(t1.id, context_summary="new summary")
    assert updated.context_summary == "new summary" and updated.last_verified > before
    moved = tree.move(t1.id, parent.id, 1)
    assert moved.last_verified > updated.last_verified
    created = tree.create(parent.id, "t3", "build", "s")
    assert created.last_verified > moved.last_verified


def test_9_worker_cannot_update_its_own_task(tree):
    project, _, _, l4 = chain_to_level_4(tree)
    task = tree.create(l4.id, "task", "build", "s")
    tree.assign(task.id, "w1")
    worker = Principal("w1", "worker", project.id, task.id)
    facts = NodeFacts(task.id, project.id, tree.get(task.id).assignee)
    assert not TablePermissionPolicy().can_edit_node(worker, facts)


def test_10_replace_content_supersedes_old_stays_readable(env):
    tree, refs = env
    parent, (t1,) = siblings(tree, 1)
    old = tree.add_content(t1.id, "version 1", ("spec",))
    new = tree.replace_content(t1.id, old.reference_id, "version 2")
    assert new.reference_id != old.reference_id
    assert tree.content(t1.id) == [new]
    assert refs.get(old.reference_id, follow_superseded=False).text == "version 1"
    assert refs.get(old.reference_id).text == "version 2"


def test_11_ancestors_root_first_with_summaries(tree):
    project, l2, l3, l4 = chain_to_level_4(tree)
    task = tree.create(l4.id, "task", "build", "s5")
    ancestors = tree.ancestors(task.id)
    assert [a.id for a in ancestors] == [project.id, l2.id, l3.id, l4.id]
    assert [a.context_summary for a in ancestors] == ["build X", "s2", "s3", "s4"]


def test_17_list_nodes_by_state(tree):
    project, l2, l3, l4 = chain_to_level_4(tree)
    t1 = tree.create(l4.id, "t1", "build", "s")
    tree.set_state(t1.id, "done")
    other = tree.create(None, "other project", "what we're doing", "s")
    all_ids = {n.id for n in tree.list_nodes(project.id)}
    assert all_ids == {project.id, l2.id, l3.id, l4.id, t1.id}
    assert other.id not in all_ids
    assert [n.id for n in tree.list_nodes(project.id, state="done")] == [t1.id]
