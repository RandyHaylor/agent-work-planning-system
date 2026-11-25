"""The node-id (`nd-`) / raw-input-id (`raw-`) display + accepted-prefix convention.

Display-only: stored ids stay bare. Inputs accept either prefixed or bare form.
"""
from __future__ import annotations

import json

from source_of_truth.cli_entrypoint import (
    _handle_read,
    _handle_search_nodes,
    _handle_show_top_level,
    _handle_show_tree,
    _handle_submit_change_set,
)
from source_of_truth.id_display import (
    format_node_id_for_display,
    format_raw_input_id_for_display,
    strip_node_id_input_prefix,
    strip_raw_input_id_input_prefix,
)
from source_of_truth.load_config import (
    ProjectSettings,
    REVIEWER_MODE_NO_REVIEWER_DIRECT_APPLY,
    save_project_settings,
)
from source_of_truth.raw_input_log_writer import append_submission_to_raw_input_log
from source_of_truth.requirements_tree_node_schema import (
    _coerce_node_id_to_string,
    _coerce_parent_id_to_string_with_top_level_sentinel,
)
from source_of_truth.requirements_tree_store import load_requirements_tree


def _seed_project(project_id: str, text: str = "the requirement text") -> int:
    save_project_settings(ProjectSettings(
        project_id=project_id, reviewer_mode_override=REVIEWER_MODE_NO_REVIEWER_DIRECT_APPLY,
    ))
    return append_submission_to_raw_input_log(project_id, "s", text, "")["raw_input_id"]


# ----- helper unit tests -----

def test_format_helpers():
    assert format_node_id_for_display("e") == "nd-e"
    assert format_node_id_for_display("2") == "nd-2"
    assert format_raw_input_id_for_display(22) == "raw-22"


def test_strip_helpers_are_no_ops_for_bare_values():
    assert strip_node_id_input_prefix("nd-2") == "2"
    assert strip_node_id_input_prefix("2") == "2"
    assert strip_node_id_input_prefix(2) == "2"
    assert strip_raw_input_id_input_prefix("raw-5") == 5
    assert strip_raw_input_id_input_prefix("5") == 5
    assert strip_raw_input_id_input_prefix(5) == 5


def test_coercion_strips_node_prefix_and_sentinel():
    assert _coerce_node_id_to_string("nd-e") == "e"
    assert _coerce_node_id_to_string("e") == "e"
    assert _coerce_parent_id_to_string_with_top_level_sentinel("nd-0") == "0"
    assert _coerce_parent_id_to_string_with_top_level_sentinel("0") == "0"
    assert _coerce_parent_id_to_string_with_top_level_sentinel("nd-e") == "e"


# ----- input acceptance: prefixed and bare forms produce the same node -----

def test_submit_accepts_nd_parent_and_raw_add(capsys):
    project_id = "p-id-prefixed"
    rid = _seed_project(project_id)
    rc = _handle_submit_change_set([
        project_id, "--add", format_raw_input_id_for_display(rid),
        "--parent", "nd-0", "--title", "prefixed leaf",
    ])
    captured = capsys.readouterr()
    assert rc == 0
    payload = json.loads(captured.out)
    assert payload["assigned_node_ids"] == ["nd-0>nd-1: prefixed leaf"]
    tree = load_requirements_tree(project_id)
    # Stored bare.
    node = tree.nodes_by_id["1"]
    assert node.node_id == "1"
    assert node.parent_id == "0"
    assert node.raw_input_reference.raw_input_id == rid


def test_submit_bare_form_matches_prefixed_form(capsys):
    project_id = "p-id-bare"
    rid = _seed_project(project_id)
    rc = _handle_submit_change_set([
        project_id, "--add", str(rid), "--parent", "0", "--title", "bare leaf",
    ])
    captured = capsys.readouterr()
    assert rc == 0
    payload = json.loads(captured.out)
    assert payload["assigned_node_ids"] == ["nd-0>nd-1: bare leaf"]


def test_json_change_set_with_prefixed_ids_normalizes(capsys):
    project_id = "p-id-json"
    rid = _seed_project(project_id)
    # First make a group to reparent under.
    _handle_submit_change_set([project_id, "--add-group", "--parent", "0", "--title", "grp"])
    capsys.readouterr()
    change_set = {
        "operations": [
            {
                "op": "add",
                "parent_id": "nd-a",
                "raw_input_reference": {"raw_input_id": format_raw_input_id_for_display(rid)},
                "short_neutral_title": "json leaf",
            }
        ]
    }
    rc = _handle_submit_change_set([project_id, json.dumps(change_set)])
    captured = capsys.readouterr()
    assert rc == 0
    tree = load_requirements_tree(project_id)
    node = tree.nodes_by_id["1"]
    assert node.parent_id == "a"
    assert node.raw_input_reference.raw_input_id == rid


# ----- display surfaces carry prefixes -----

def test_show_tree_and_top_level_use_nd_prefix(capsys):
    project_id = "p-id-showtree"
    rid = _seed_project(project_id, "show tree quote")
    _handle_submit_change_set([
        project_id, "--add", str(rid), "--parent", "0", "--title", "leafy",
    ])
    capsys.readouterr()

    _handle_show_tree([project_id])
    assert "nd-1 leafy" in capsys.readouterr().out

    _handle_show_tree([project_id, "--show-all"])
    show_all = capsys.readouterr().out
    assert "[nd-1]" in show_all
    assert "raw-" in show_all

    _handle_show_top_level([project_id])
    assert "nd-1 leafy" in capsys.readouterr().out


def test_search_and_read_carry_prefixes(capsys):
    project_id = "p-id-readsearch"
    rid = _seed_project(project_id, "unique searchable phrase")
    _handle_submit_change_set([
        project_id, "--add", str(rid), "--parent", "0", "--title", "findme",
    ])
    capsys.readouterr()

    _handle_search_nodes([project_id, "searchable"])
    search_out = json.loads(capsys.readouterr().out)
    match_display = search_out["matches"][0]["display"]
    assert match_display.startswith("nd-1: findme - raw-")
    assert "unique searchable phrase" in match_display

    # read accepts an nd- prefixed id and returns a display field with both prefixes,
    # while keeping the structured node's ids bare.
    _handle_read([project_id, "nd-1"])
    read_out = json.loads(capsys.readouterr().out)
    node_payload = read_out[0]
    assert node_payload["node"]["node_id"] == "1"
    assert node_payload["node"]["raw_input_reference"]["raw_input_id"] == rid
    assert node_payload["display"].startswith("nd-1: findme - raw-")


# ----- on-disk storage stays bare -----

def test_on_disk_ids_remain_bare(capsys):
    project_id = "p-id-ondisk"
    rid = _seed_project(project_id)
    _handle_submit_change_set([
        project_id, "--add", "raw-" + str(rid), "--parent", "nd-0", "--title", "x",
    ])
    capsys.readouterr()
    from source_of_truth.load_config import project_source_of_truth_file_path
    raw_json = json.loads(project_source_of_truth_file_path(project_id).read_text())
    assert "1" in raw_json["nodes_by_id"]
    assert raw_json["nodes_by_id"]["1"]["node_id"] == "1"
    assert raw_json["nodes_by_id"]["1"]["raw_input_reference"]["raw_input_id"] == rid
    assert "nd-1" not in raw_json["nodes_by_id"]
