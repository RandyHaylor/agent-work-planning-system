"""T9: CLI shortcut forms (combo first, leaf, group)."""
from __future__ import annotations

import pytest

from source_of_truth.cli_entrypoint import _resolve_change_set_payload_from_argv_after_project_id
from source_of_truth.requirements_tree_node_schema import RequirementsTree
from source_of_truth.requirements_tree_store import save_requirements_tree_atomically


def test_combo_shortcut_emits_two_ops_add_group_then_add_leaf_under_it():
    save_requirements_tree_atomically(RequirementsTree.empty_for_project("p-combo1"))
    payload = _resolve_change_set_payload_from_argv_after_project_id(
        [
            "--add", "42", "--parent", "0", "--title", "vendor placement",
            "--new-group", "vendor rules",
        ],
        project_id_for_combo_letter_lookup="p-combo1",
    )
    ops = payload["operations"]
    assert len(ops) == 2
    assert ops[0]["op"] == "add_group"
    assert ops[0]["parent_id"] == "0"
    assert ops[0]["short_neutral_title"] == "vendor rules"
    # Leaf op's parent_id must be the letter id the new group will get -- "a"
    # for an empty tree.
    assert ops[1]["op"] == "add"
    assert ops[1]["parent_id"] == "a"
    assert ops[1]["short_neutral_title"] == "vendor placement"
    assert ops[1]["raw_input_reference"]["raw_input_id"] == 42


def test_leaf_only_shortcut_emits_one_add_op_under_explicit_parent():
    payload = _resolve_change_set_payload_from_argv_after_project_id([
        "--add", "42", "--parent", "a", "--title", "vendor placement",
    ])
    ops = payload["operations"]
    assert len(ops) == 1
    assert ops[0]["op"] == "add"
    assert ops[0]["parent_id"] == "a"
    assert ops[0]["short_neutral_title"] == "vendor placement"
    assert ops[0]["raw_input_reference"]["raw_input_id"] == 42


def test_group_only_shortcut_emits_one_add_group_op():
    payload = _resolve_change_set_payload_from_argv_after_project_id([
        "--add-group", "--parent", "0", "--title", "vendor rules",
    ])
    ops = payload["operations"]
    assert len(ops) == 1
    assert ops[0]["op"] == "add_group"
    assert ops[0]["parent_id"] == "0"
    assert ops[0]["short_neutral_title"] == "vendor rules"


def test_leaf_shortcut_missing_title_raises():
    with pytest.raises(ValueError, match="title"):
        _resolve_change_set_payload_from_argv_after_project_id([
            "--add", "42", "--parent", "0",
        ])


def test_leaf_shortcut_missing_parent_raises():
    with pytest.raises(ValueError, match="parent"):
        _resolve_change_set_payload_from_argv_after_project_id([
            "--add", "42", "--title", "x",
        ])


def test_group_shortcut_missing_title_raises():
    with pytest.raises(ValueError, match="title"):
        _resolve_change_set_payload_from_argv_after_project_id([
            "--add-group", "--parent", "0",
        ])
