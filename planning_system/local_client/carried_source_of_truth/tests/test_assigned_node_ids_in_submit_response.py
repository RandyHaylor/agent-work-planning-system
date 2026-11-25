"""Submit response surfaces newly-assigned node ids in compact `<parent>><assigned>: <title>` form."""
from __future__ import annotations

import json

from source_of_truth.cli_entrypoint import _handle_submit_change_set
from source_of_truth.load_config import (
    ProjectSettings,
    REVIEWER_MODE_NO_REVIEWER_DIRECT_APPLY,
    save_project_settings,
)
from source_of_truth.raw_input_log_writer import append_submission_to_raw_input_log


def _seed_project(project_id: str) -> int:
    save_project_settings(ProjectSettings(
        project_id=project_id, reviewer_mode_override=REVIEWER_MODE_NO_REVIEWER_DIRECT_APPLY,
    ))
    log_result = append_submission_to_raw_input_log(project_id, "s", "raw text", "")
    return log_result["raw_input_id"]


def test_submit_response_for_combo_lists_both_new_node_ids_with_parent_arrow_and_title(capsys):
    project_id = "p-assigned-combo"
    raw_input_id = _seed_project(project_id)
    rc = _handle_submit_change_set([
        project_id,
        "--add", str(raw_input_id),
        "--parent", "0", "--title", "ui color scheme",
        "--new-group", "ui interface",
    ])
    captured = capsys.readouterr()
    assert rc == 0
    payload = json.loads(captured.out)
    assigned_lines = payload["assigned_node_ids"]
    assert assigned_lines == ["nd-0>nd-a: ui interface", "nd-a>nd-1: ui color scheme"]


def test_submit_response_for_leaf_only_lists_one_assignment_line(capsys):
    project_id = "p-assigned-leaf"
    raw_input_id = _seed_project(project_id)
    rc = _handle_submit_change_set([
        project_id,
        "--add", str(raw_input_id),
        "--parent", "0", "--title", "back end stack",
    ])
    captured = capsys.readouterr()
    assert rc == 0
    payload = json.loads(captured.out)
    assigned_lines = payload["assigned_node_ids"]
    assert assigned_lines == ["nd-0>nd-1: back end stack"]


def test_submit_response_for_group_only_lists_one_assignment_line(capsys):
    project_id = "p-assigned-group"
    _seed_project(project_id)
    rc = _handle_submit_change_set([
        project_id,
        "--add-group", "--parent", "0", "--title", "vendor rules",
    ])
    captured = capsys.readouterr()
    assert rc == 0
    payload = json.loads(captured.out)
    assigned_lines = payload["assigned_node_ids"]
    assert assigned_lines == ["nd-0>nd-a: vendor rules"]


def test_submit_response_assigned_lines_empty_when_no_add_or_add_group_ops(capsys):
    project_id = "p-no-assign"
    raw_input_id = _seed_project(project_id)
    # First, add a leaf so we have something to remove.
    _handle_submit_change_set([
        project_id, "--add", str(raw_input_id), "--parent", "0", "--title", "victim",
    ])
    capsys.readouterr()
    # Now submit a remove op via JSON form.
    rc = _handle_submit_change_set([
        project_id,
        json.dumps({"operations": [{"op": "remove", "node_id": "1"}]}),
    ])
    captured = capsys.readouterr()
    assert rc == 0
    payload = json.loads(captured.out)
    assert payload["assigned_node_ids"] == []
