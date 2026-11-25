"""T7: `add` op requires parent_node_id + short_neutral_title (1-50 chars). add_top_level op kind dropped."""
from __future__ import annotations

import pytest

from source_of_truth.requirements_tree_change_set_applier import (
    ChangeSetApplicationError,
    apply_change_set_to_tree,
)
from source_of_truth.requirements_tree_node_schema import (
    QUOTE_REFERENCE_NODE_KIND,
    TOP_LEVEL_PARENT_SENTINEL,
    RequirementsTree,
)


def test_add_op_with_parent_zero_and_one_to_fifty_char_title_succeeds():
    tree = RequirementsTree.empty_for_project("p")
    new_tree = apply_change_set_to_tree(tree, [{
        "op": "add",
        "parent_id": TOP_LEVEL_PARENT_SENTINEL,
        "raw_input_reference": {"raw_input_id": 0},
        "short_neutral_title": "vendor placement",
    }])
    assert "1" in new_tree.nodes_by_id
    assert new_tree.nodes_by_id["1"].kind == QUOTE_REFERENCE_NODE_KIND
    assert new_tree.nodes_by_id["1"].short_neutral_title == "vendor placement"
    assert new_tree.nodes_by_id["1"].parent_id == TOP_LEVEL_PARENT_SENTINEL


def test_add_op_missing_parent_id_field_raises():
    tree = RequirementsTree.empty_for_project("p")
    with pytest.raises(ChangeSetApplicationError, match="parent_id"):
        apply_change_set_to_tree(tree, [{
            "op": "add",
            "raw_input_reference": {"raw_input_id": 0},
            "short_neutral_title": "x",
        }])


def test_add_op_with_empty_title_raises():
    tree = RequirementsTree.empty_for_project("p")
    with pytest.raises(ChangeSetApplicationError, match="short_neutral_title"):
        apply_change_set_to_tree(tree, [{
            "op": "add",
            "parent_id": TOP_LEVEL_PARENT_SENTINEL,
            "raw_input_reference": {"raw_input_id": 0},
            "short_neutral_title": "",
        }])


def test_add_op_with_missing_title_field_raises():
    tree = RequirementsTree.empty_for_project("p")
    with pytest.raises(ChangeSetApplicationError, match="short_neutral_title"):
        apply_change_set_to_tree(tree, [{
            "op": "add",
            "parent_id": TOP_LEVEL_PARENT_SENTINEL,
            "raw_input_reference": {"raw_input_id": 0},
        }])


def test_add_op_with_title_over_fifty_chars_raises():
    tree = RequirementsTree.empty_for_project("p")
    too_long_title = "x" * 51
    with pytest.raises(ChangeSetApplicationError, match="50"):
        apply_change_set_to_tree(tree, [{
            "op": "add",
            "parent_id": TOP_LEVEL_PARENT_SENTINEL,
            "raw_input_reference": {"raw_input_id": 0},
            "short_neutral_title": too_long_title,
        }])


def test_add_group_op_also_requires_one_to_fifty_char_title():
    tree = RequirementsTree.empty_for_project("p")
    with pytest.raises(ChangeSetApplicationError, match="short_neutral_title"):
        apply_change_set_to_tree(tree, [{
            "op": "add_group",
            "parent_id": TOP_LEVEL_PARENT_SENTINEL,
            "short_neutral_title": "",
        }])
    with pytest.raises(ChangeSetApplicationError, match="50"):
        apply_change_set_to_tree(tree, [{
            "op": "add_group",
            "parent_id": TOP_LEVEL_PARENT_SENTINEL,
            "short_neutral_title": "x" * 51,
        }])


def test_add_top_level_op_kind_no_longer_recognized():
    tree = RequirementsTree.empty_for_project("p")
    with pytest.raises(ChangeSetApplicationError, match="Unknown op kind: add_top_level"):
        apply_change_set_to_tree(tree, [{
            "op": "add_top_level",
            "raw_input_reference": {"raw_input_id": 0},
        }])
