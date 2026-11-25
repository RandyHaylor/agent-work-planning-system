"""Cover per-op apply isolation: one bad op should not sink the others."""
from __future__ import annotations

import pytest

from source_of_truth.requirements_tree_change_set_applier import (
    apply_change_set_to_tree,
    apply_change_set_to_tree_with_per_op_isolation,
)
from source_of_truth.requirements_tree_node_schema import RequirementsTree


def _seed_tree_with_one_top_level_node() -> RequirementsTree:
    tree = RequirementsTree.empty_for_project("p")
    return apply_change_set_to_tree(tree, [
        {"op": "add", "parent_id": "0", "raw_input_reference": {"raw_input_id": 0}, "short_neutral_title": "seed"}
    ])


def test_isolation_applies_good_ops_and_skips_only_the_bad_one():
    tree = _seed_tree_with_one_top_level_node()
    valid_top_node_id = tree.list_top_level_node_ids()[0]
    operations = [
        {"op": "add", "parent_id": "0", "raw_input_reference": {"raw_input_id": 1}, "short_neutral_title": "n1"},
        {"op": "remove", "node_id": "99999"},  # bad: nonexistent node
        {"op": "add", "parent_id": "0", "raw_input_reference": {"raw_input_id": 2}, "short_neutral_title": "n2"},
    ]
    new_tree, outcomes = apply_change_set_to_tree_with_per_op_isolation(tree, operations)
    assert outcomes[0]["operation_index"] == 0
    assert outcomes[0]["applied"] is True
    assert outcomes[1]["applied"] is False
    assert outcomes[1]["operation_index"] == 1
    assert "99999" in outcomes[1]["error"]
    assert outcomes[2]["operation_index"] == 2
    assert outcomes[2]["applied"] is True
    # Tree should have the original 1 node + 2 newly added top-level = 3 total.
    assert len(new_tree.nodes_by_id) == 3


def test_all_ops_succeed_returns_all_applied_true():
    tree = _seed_tree_with_one_top_level_node()
    operations = [
        {"op": "add", "parent_id": "0", "raw_input_reference": {"raw_input_id": 5}, "short_neutral_title": "n5"},
        {"op": "add", "parent_id": "0", "raw_input_reference": {"raw_input_id": 6}, "short_neutral_title": "n6"},
    ]
    new_tree, outcomes = apply_change_set_to_tree_with_per_op_isolation(tree, operations)
    assert all(o["applied"] for o in outcomes)
    assert len(new_tree.nodes_by_id) == 3


def test_empty_operations_list_returns_unchanged_tree_and_no_outcomes():
    tree = _seed_tree_with_one_top_level_node()
    new_tree, outcomes = apply_change_set_to_tree_with_per_op_isolation(tree, [])
    assert outcomes == []
    assert new_tree.to_json_dict() == tree.to_json_dict()


def test_input_tree_is_not_mutated_by_isolation_apply():
    import copy
    tree = _seed_tree_with_one_top_level_node()
    snapshot_before = copy.deepcopy(tree.to_json_dict())
    apply_change_set_to_tree_with_per_op_isolation(tree, [
        {"op": "add", "parent_id": "0", "raw_input_reference": {"raw_input_id": 9}, "short_neutral_title": "n9"},
        {"op": "remove", "node_id": "99999"},
    ])
    assert tree.to_json_dict() == snapshot_before
