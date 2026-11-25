"""T5: add_group op creates a group node with auto-allocated letter id."""
from __future__ import annotations

import pytest

from source_of_truth.requirements_tree_change_set_applier import (
    ChangeSetApplicationError,
    apply_change_set_to_tree,
)
from source_of_truth.requirements_tree_node_schema import (
    GROUP_NODE_KIND,
    TOP_LEVEL_PARENT_SENTINEL,
    RequirementsTree,
)


def test_first_add_group_op_creates_top_level_group_with_letter_id_a():
    tree = RequirementsTree.empty_for_project("p")
    new_tree = apply_change_set_to_tree(tree, [{
        "op": "add_group",
        "parent_id": TOP_LEVEL_PARENT_SENTINEL,
        "short_neutral_title": "vendor placement rules",
    }])
    assert "a" in new_tree.nodes_by_id
    assert new_tree.nodes_by_id["a"].kind == GROUP_NODE_KIND
    assert new_tree.nodes_by_id["a"].parent_id == TOP_LEVEL_PARENT_SENTINEL
    assert new_tree.nodes_by_id["a"].short_neutral_title == "vendor placement rules"
    assert new_tree.next_group_letter_index == 1
    assert "a" in new_tree.list_top_level_node_ids()


def test_subsequent_add_group_ops_get_b_c_d_in_order():
    tree = RequirementsTree.empty_for_project("p")
    ops = [
        {"op": "add_group", "parent_id": "0", "short_neutral_title": "first"},
        {"op": "add_group", "parent_id": "0", "short_neutral_title": "second"},
        {"op": "add_group", "parent_id": "0", "short_neutral_title": "third"},
    ]
    new_tree = apply_change_set_to_tree(tree, ops)
    assert "a" in new_tree.nodes_by_id
    assert "b" in new_tree.nodes_by_id
    assert "c" in new_tree.nodes_by_id
    assert new_tree.nodes_by_id["a"].short_neutral_title == "first"
    assert new_tree.nodes_by_id["b"].short_neutral_title == "second"
    assert new_tree.nodes_by_id["c"].short_neutral_title == "third"
    assert new_tree.next_group_letter_index == 3


def test_add_group_with_existing_parent_attaches_as_child():
    tree = RequirementsTree.empty_for_project("p")
    # Seed a parent group "a" first.
    tree = apply_change_set_to_tree(tree, [
        {"op": "add_group", "parent_id": "0", "short_neutral_title": "parent group"}
    ])
    # Now add a child group whose parent is "a".
    new_tree = apply_change_set_to_tree(tree, [
        {"op": "add_group", "parent_id": "a", "short_neutral_title": "child group"}
    ])
    assert "b" in new_tree.nodes_by_id
    assert new_tree.nodes_by_id["b"].parent_id == "a"
    assert "b" in new_tree.nodes_by_id["a"].child_node_ids
    assert "b" not in new_tree.list_top_level_node_ids()


def test_add_group_with_unknown_parent_raises_application_error():
    tree = RequirementsTree.empty_for_project("p")
    with pytest.raises(ChangeSetApplicationError):
        apply_change_set_to_tree(tree, [
            {"op": "add_group", "parent_id": "zz_missing", "short_neutral_title": "x"}
        ])


def test_letter_index_persists_across_subsequent_change_set_applications():
    tree = RequirementsTree.empty_for_project("p")
    tree = apply_change_set_to_tree(tree, [
        {"op": "add_group", "parent_id": "0", "short_neutral_title": "g1"},
        {"op": "add_group", "parent_id": "0", "short_neutral_title": "g2"},
    ])
    # Round-trip through JSON to simulate persistence.
    persisted = RequirementsTree.from_json_dict(tree.to_json_dict())
    new_tree = apply_change_set_to_tree(persisted, [
        {"op": "add_group", "parent_id": "0", "short_neutral_title": "g3"}
    ])
    assert "c" in new_tree.nodes_by_id
    assert new_tree.next_group_letter_index == 3
