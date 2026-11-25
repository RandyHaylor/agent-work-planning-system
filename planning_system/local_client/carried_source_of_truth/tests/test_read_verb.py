"""T6: `read` verb (renamed from `get-node`) accepts multiple ids; mixed leaf + group."""
from __future__ import annotations

import json

from source_of_truth.cli_entrypoint import _handle_read, _handle_submit_change_set
from source_of_truth.load_config import (
    ProjectSettings,
    REVIEWER_MODE_NO_REVIEWER_DIRECT_APPLY,
    save_project_settings,
)
from source_of_truth.raw_input_log_writer import append_submission_to_raw_input_log
from source_of_truth.requirements_tree_node_schema import RequirementsTree
from source_of_truth.requirements_tree_store import save_requirements_tree_atomically


def _seed_project_with_one_quote_leaf_and_one_group(project_id: str) -> int:
    save_project_settings(ProjectSettings(
        project_id=project_id, reviewer_mode_override=REVIEWER_MODE_NO_REVIEWER_DIRECT_APPLY,
    ))
    log_result = append_submission_to_raw_input_log(
        project_id, "session-x", "raw user submission text", ""
    )
    raw_input_id = log_result["raw_input_id"]
    _handle_submit_change_set([
        project_id,
        json.dumps({"operations": [{
            "op": "add", "parent_id": "0",
            "raw_input_reference": {"raw_input_id": raw_input_id},
            "short_neutral_title": "seed leaf",
        }]}),
    ])
    _handle_submit_change_set([
        project_id,
        json.dumps({
            "operations": [
                {"op": "add_group", "parent_id": "0", "short_neutral_title": "vendor placement"}
            ],
        }),
    ])
    return raw_input_id


def test_read_one_quote_leaf_id_returns_node_payload(capsys):
    _seed_project_with_one_quote_leaf_and_one_group("p-read1")
    capsys.readouterr()
    rc = _handle_read(["p-read1", "1"])
    captured = capsys.readouterr()
    assert rc == 0
    parsed = json.loads(captured.out)
    assert isinstance(parsed, list)
    assert len(parsed) == 1
    assert parsed[0]["node"]["node_id"] == "1"


def test_read_multiple_ids_returns_each_in_order_including_group_letter_id(capsys):
    _seed_project_with_one_quote_leaf_and_one_group("p-read2")
    capsys.readouterr()
    rc = _handle_read(["p-read2", "a", "1"])
    captured = capsys.readouterr()
    assert rc == 0
    parsed = json.loads(captured.out)
    assert len(parsed) == 2
    assert parsed[0]["node"]["node_id"] == "a"
    assert parsed[0]["node"]["kind"] == "group"
    assert parsed[1]["node"]["node_id"] == "1"


def test_read_unknown_id_emits_error_entry_for_that_id_only(capsys):
    _seed_project_with_one_quote_leaf_and_one_group("p-read3")
    capsys.readouterr()
    rc = _handle_read(["p-read3", "1", "zz_missing"])
    captured = capsys.readouterr()
    parsed = json.loads(captured.out)
    assert len(parsed) == 2
    assert parsed[0]["node"]["node_id"] == "1"
    assert "error" in parsed[1]
    assert "zz_missing" in parsed[1]["error"]
    assert rc == 1  # at least one id failed


def test_read_with_zero_ids_returns_usage_error(capsys):
    # With the project resolved (its id names a real project on disk), passing no
    # node ids is a usage error.
    _seed_project_with_one_quote_leaf_and_one_group("p-readempty")
    rc = _handle_read(["p-readempty"])
    assert rc == 2
