"""Tests for the runtime-facing CLI verbs added so the agent has a sanctioned
invocation surface for the controlled API."""
from __future__ import annotations

import io
import json
import sys
from unittest.mock import patch

import pytest

from source_of_truth.cli_entrypoint import (
    _build_per_turn_additional_context_line,
    _handle_get_node,
    _handle_search_nodes,
    _handle_show_tree,
    _handle_submit_change_set,
    _resolve_change_set_payload_from_argv_after_project_id,
)
from source_of_truth.load_config import (
    ProjectSettings,
    REVIEWER_MODE_NO_REVIEWER_DIRECT_APPLY,
    save_project_settings,
)
from source_of_truth.raw_input_log_writer import append_submission_to_raw_input_log
from source_of_truth.requirements_tree_store import (
    load_requirements_tree,
    save_requirements_tree_atomically,
)
from source_of_truth.requirements_tree_node_schema import RequirementsTree


def _build_one_op_top_level_leaf_change_set_json(raw_input_id: int, short_title: str = "test t") -> str:
    return json.dumps({
        "operations": [{
            "op": "add",
            "parent_id": "0",
            "raw_input_reference": {"raw_input_id": raw_input_id},
            "short_neutral_title": short_title,
        }],
    })


def test_per_turn_additional_context_line_is_one_line_with_two_commands():
    line = _build_per_turn_additional_context_line(project_id="proj-x", raw_input_id=42)
    assert "\n" not in line, "must be a single line"
    assert "raw-42" in line  # raw input id shown with the raw- display prefix
    assert "source-of-truth submit-change-set --add 42" in line
    assert "source-of-truth show-tree" in line
    assert "SKILL.md" in line
    # Project id is resolved from the session -- never shown to the agent.
    assert "proj-x" not in line


def test_add_top_level_shortcut_no_longer_exists():
    """The --add-top-level convenience flag was removed in T7 to force the agent
    to think about parent_node_id and short_neutral_title. JSON form is the only
    path until T9 introduces the new flag forms."""
    with pytest.raises(ValueError):
        _resolve_change_set_payload_from_argv_after_project_id(
            ["--add-top-level", "7"]
        )


def test_resolve_change_set_payload_from_stdin():
    stdin_content = json.dumps({
        "submitter_rationale": "via stdin",
        "operations": [{"op": "add_top_level", "raw_input_reference": {"raw_input_id": 3}}],
    })
    payload = _resolve_change_set_payload_from_argv_after_project_id(
        ["-"], stdin_text_supplier=lambda: stdin_content,
    )
    assert payload["submitter_rationale"] == "via stdin"


def test_resolve_change_set_payload_from_atfile(tmp_path):
    file_path = tmp_path / "cs.json"
    file_path.write_text(json.dumps({
        "operations": [{"op": "add_top_level", "raw_input_reference": {"raw_input_id": 9}}],
    }))
    payload = _resolve_change_set_payload_from_argv_after_project_id(
        [f"@{file_path}"]
    )
    assert payload["operations"][0]["raw_input_reference"]["raw_input_id"] == 9


def test_resolve_change_set_payload_from_raw_json_argv():
    raw_json = json.dumps({
        "operations": [{"op": "add_top_level", "raw_input_reference": {"raw_input_id": 5}}],
    })
    payload = _resolve_change_set_payload_from_argv_after_project_id([raw_json])
    assert payload["operations"][0]["raw_input_reference"]["raw_input_id"] == 5


def test_submit_change_set_short_form_applies_under_no_reviewer_mode(capsys):
    save_project_settings(ProjectSettings(
        project_id="p-cli", reviewer_mode_override=REVIEWER_MODE_NO_REVIEWER_DIRECT_APPLY,
    ))
    log_result = append_submission_to_raw_input_log("p-cli", "s", "yes", "")
    raw_input_id = log_result["raw_input_id"]
    return_code = _handle_submit_change_set(["p-cli", _build_one_op_top_level_leaf_change_set_json(raw_input_id)])
    captured = capsys.readouterr()
    assert return_code == 0
    payload = json.loads(captured.out)
    assert payload["approved"] is True
    assert payload["applied_operation_count"] == 1
    tree = load_requirements_tree("p-cli")
    assert len(tree.nodes_by_id) == 1


def test_show_tree_renders_compact_listing_for_empty_tree(capsys):
    save_requirements_tree_atomically(RequirementsTree.empty_for_project("p-show"))
    rc = _handle_show_tree(["p-show"])
    captured = capsys.readouterr()
    assert rc == 0
    assert "p-show" in captured.out
    assert "0 nodes" in captured.out


def test_show_tree_show_all_flag_inlines_quote_text_for_top_level_nodes(capsys):
    save_project_settings(ProjectSettings(
        project_id="p-show2", reviewer_mode_override=REVIEWER_MODE_NO_REVIEWER_DIRECT_APPLY,
    ))
    log_result = append_submission_to_raw_input_log(
        "p-show2", "session-x", "the actual requirement text the user typed", ""
    )
    _handle_submit_change_set(["p-show2", _build_one_op_top_level_leaf_change_set_json(log_result["raw_input_id"])])
    capsys.readouterr()
    rc = _handle_show_tree(["p-show2", "--show-all"])
    captured = capsys.readouterr()
    assert rc == 0
    assert "the actual requirement text the user typed" in captured.out
    assert "[nd-1]" in captured.out
    assert "raw-" in captured.out


def test_get_node_returns_node_payload_for_existing_id(capsys):
    save_project_settings(ProjectSettings(
        project_id="p-get", reviewer_mode_override=REVIEWER_MODE_NO_REVIEWER_DIRECT_APPLY,
    ))
    log_result = append_submission_to_raw_input_log("p-get", "s", "x", "")
    _handle_submit_change_set(["p-get", _build_one_op_top_level_leaf_change_set_json(log_result["raw_input_id"])])
    capsys.readouterr()  # discard submit output

    rc = _handle_get_node(["p-get", "1"])
    captured = capsys.readouterr()
    assert rc == 0
    parsed = json.loads(captured.out)
    # `read` (and its get-node alias) now returns a list of per-id payloads.
    assert parsed[0]["node"]["node_id"] == "1"


def test_get_node_returns_error_for_missing_id(capsys):
    save_requirements_tree_atomically(RequirementsTree.empty_for_project("p-missing"))
    rc = _handle_get_node(["p-missing", "999"])
    captured = capsys.readouterr()
    assert rc == 1
    parsed = json.loads(captured.out)
    assert "not found" in parsed[0]["error"]


def test_search_nodes_returns_matches_payload(capsys):
    save_project_settings(ProjectSettings(
        project_id="p-search", reviewer_mode_override=REVIEWER_MODE_NO_REVIEWER_DIRECT_APPLY,
    ))
    log_result = append_submission_to_raw_input_log("p-search", "s", "haystack needle haystack", "")
    _handle_submit_change_set(["p-search", _build_one_op_top_level_leaf_change_set_json(log_result["raw_input_id"])])
    capsys.readouterr()

    rc = _handle_search_nodes(["p-search", "needle"])
    captured = capsys.readouterr()
    assert rc == 0
    parsed = json.loads(captured.out)
    assert isinstance(parsed.get("matches"), list)
    assert len(parsed["matches"]) == 1
