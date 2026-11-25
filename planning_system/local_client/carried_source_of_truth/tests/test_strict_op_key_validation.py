"""Reject ops that contain unknown keys, so silent drops don't deceive the submitting agent."""
from __future__ import annotations

import pytest

from source_of_truth.requirements_tree_change_set_applier import (
    ChangeSetApplicationError,
    apply_change_set_to_tree,
)
from source_of_truth.requirements_tree_node_schema import RequirementsTree


def _seed_tree_with_one_top_level_leaf_and_one_group() -> RequirementsTree:
    tree = RequirementsTree.empty_for_project("p")
    return apply_change_set_to_tree(tree, [
        {"op": "add", "parent_id": "0", "raw_input_reference": {"raw_input_id": 0},
         "short_neutral_title": "seed"},
        {"op": "add_group", "parent_id": "0", "short_neutral_title": "seed g"},
    ])


def test_add_op_with_unknown_field_cited_slice_raises():
    tree = RequirementsTree.empty_for_project("p")
    with pytest.raises(ChangeSetApplicationError, match="unknown.*cited_slice"):
        apply_change_set_to_tree(tree, [{
            "op": "add", "parent_id": "0",
            "raw_input_reference": {"raw_input_id": 0},
            "short_neutral_title": "x",
            "cited_slice": "user typed text agent invented this field",
        }])


def test_add_group_op_with_unknown_field_raises():
    tree = RequirementsTree.empty_for_project("p")
    with pytest.raises(ChangeSetApplicationError, match="unknown.*notes"):
        apply_change_set_to_tree(tree, [{
            "op": "add_group", "parent_id": "0",
            "short_neutral_title": "g",
            "notes": "extra field",
        }])


def test_reparent_op_with_unknown_field_raises():
    tree = _seed_tree_with_one_top_level_leaf_and_one_group()
    with pytest.raises(ChangeSetApplicationError, match="unknown.*reason"):
        apply_change_set_to_tree(tree, [{
            "op": "reparent", "node_id": "1", "new_parent_id": "a",
            "reason": "agent invented reason field",
        }])


def test_remove_op_with_unknown_field_raises():
    tree = _seed_tree_with_one_top_level_leaf_and_one_group()
    with pytest.raises(ChangeSetApplicationError, match="unknown.*explanation"):
        apply_change_set_to_tree(tree, [{
            "op": "remove", "node_id": "1",
            "explanation": "agent invented explanation field",
        }])


def test_modify_reference_op_with_unknown_field_raises():
    tree = _seed_tree_with_one_top_level_leaf_and_one_group()
    with pytest.raises(ChangeSetApplicationError, match="unknown.*comment"):
        apply_change_set_to_tree(tree, [{
            "op": "modify_reference", "node_id": "1",
            "raw_input_reference": {"raw_input_id": 5},
            "comment": "agent invented comment field",
        }])


def test_reorder_children_op_with_unknown_field_raises():
    tree = RequirementsTree.empty_for_project("p")
    tree = apply_change_set_to_tree(tree, [
        {"op": "add_group", "parent_id": "0", "short_neutral_title": "g"},
        {"op": "add", "parent_id": "a", "raw_input_reference": {"raw_input_id": 0},
         "short_neutral_title": "c1"},
        {"op": "add", "parent_id": "a", "raw_input_reference": {"raw_input_id": 1},
         "short_neutral_title": "c2"},
    ])
    children = list(tree.nodes_by_id["a"].child_node_ids)
    with pytest.raises(ChangeSetApplicationError, match="unknown.*hint"):
        apply_change_set_to_tree(tree, [{
            "op": "reorder_children", "parent_id": "a",
            "child_order": list(reversed(children)),
            "hint": "agent invented hint field",
        }])


def test_add_op_error_message_lists_recognized_field_names():
    """When rejecting unknown fields, mention the fields that ARE recognized."""
    tree = RequirementsTree.empty_for_project("p")
    try:
        apply_change_set_to_tree(tree, [{
            "op": "add", "parent_id": "0",
            "raw_input_reference": {"raw_input_id": 0},
            "short_neutral_title": "x",
            "made_up": "y",
        }])
        assert False, "expected ChangeSetApplicationError"
    except ChangeSetApplicationError as exc:
        message = str(exc)
        for recognized_field in ("op", "parent_id", "raw_input_reference", "short_neutral_title"):
            assert recognized_field in message, f"error should list recognized field {recognized_field!r}: {message}"
