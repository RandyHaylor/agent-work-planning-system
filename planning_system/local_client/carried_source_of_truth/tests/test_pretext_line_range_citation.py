"""Per-node agent pre-text selection: whole / line-range / none, the `pretext`
verb, resolution, validation, and the one-project-per-session guard."""
from __future__ import annotations

import json

import pytest

from source_of_truth import cli_entrypoint, load_config
from source_of_truth.add_session_to_project_cli import (
    SessionAlreadyInDifferentProjectError,
    add_session_to_project,
)
from source_of_truth.raw_input_log_writer import append_submission_to_raw_input_log
from source_of_truth.raw_input_log_reader import (
    resolve_quote_text_from_reference,
    select_pre_text,
)
from source_of_truth.requirements_reference_validator import (
    ReferenceValidationError,
    validate_raw_input_reference,
)
from source_of_truth.requirements_tree_node_schema import (
    QUOTE_REFERENCE_NODE_KIND,
    RawInputReference,
    RequirementsTree,
    RequirementsTreeNode,
)
from source_of_truth.requirements_tree_store import (
    load_requirements_tree,
    save_requirements_tree_atomically,
)

THREE_LINE_PRETEXT = "agent line one\nagent line two\nagent line three"


def _seed_project_with_entry_and_one_quote_node(project_id, session_id, monkeypatch):
    add_session_to_project(project_id, session_id, "/tmp/s.jsonl")
    append_submission_to_raw_input_log(project_id, session_id, "the user reply", THREE_LINE_PRETEXT)
    node = RequirementsTreeNode(
        node_id="1", parent_id="0", kind=QUOTE_REFERENCE_NODE_KIND,
        raw_input_reference=RawInputReference(raw_input_id=0), short_neutral_title="topic",
    )
    tree = RequirementsTree(project_id=project_id, next_node_id=2, nodes_by_id={"1": node})
    save_requirements_tree_atomically(tree)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", session_id)


def test_select_pre_text_modes():
    assert select_pre_text(THREE_LINE_PRETEXT, None) == THREE_LINE_PRETEXT       # all
    assert select_pre_text(THREE_LINE_PRETEXT, "none") == ""                     # none
    assert select_pre_text(THREE_LINE_PRETEXT, [2, 3]) == "agent line two\nagent line three"
    assert select_pre_text("", None) == ""                                       # empty entry


def test_resolve_includes_pretext_by_default_and_honors_selection(monkeypatch):
    _seed_project_with_entry_and_one_quote_node("pj", "pj", monkeypatch)
    whole = resolve_quote_text_from_reference("pj", 0, None, None)
    assert "[agent pre-text]" in whole and "agent line one" in whole and "[user submission]" in whole
    sliced = resolve_quote_text_from_reference("pj", 0, None, [3, 3])
    assert "agent line three" in sliced and "agent line one" not in sliced
    none = resolve_quote_text_from_reference("pj", 0, None, "none")
    assert none == "the user reply"  # back-compat: submission only


def test_pretext_verb_sets_range_none_all(monkeypatch):
    _seed_project_with_entry_and_one_quote_node("pv", "pv", monkeypatch)

    assert cli_entrypoint._handle_pretext(["1", "2", "3"]) == 0
    assert load_requirements_tree("pv").nodes_by_id["1"].raw_input_reference.pre_text_line_range == [2, 3]

    assert cli_entrypoint._handle_pretext(["1", "--none"]) == 0
    assert load_requirements_tree("pv").nodes_by_id["1"].raw_input_reference.pre_text_line_range == "none"

    assert cli_entrypoint._handle_pretext(["1", "--all"]) == 0
    assert load_requirements_tree("pv").nodes_by_id["1"].raw_input_reference.pre_text_line_range is None


def test_pretext_verb_rejects_out_of_bounds_range(monkeypatch):
    _seed_project_with_entry_and_one_quote_node("pb", "pb", monkeypatch)
    assert cli_entrypoint._handle_pretext(["1", "1", "99"]) == 1  # only 3 lines
    assert load_requirements_tree("pb").nodes_by_id["1"].raw_input_reference.pre_text_line_range is None


def test_pretext_verb_refuses_when_session_not_enrolled(monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "orphan-session")
    assert cli_entrypoint._handle_pretext(["1", "--all"]) == 1  # not in any project


def test_validator_rejects_out_of_bounds_pre_text_line_range(monkeypatch):
    _seed_project_with_entry_and_one_quote_node("vv", "vv", monkeypatch)
    with pytest.raises(ReferenceValidationError):
        validate_raw_input_reference("vv", {"raw_input_id": 0, "pre_text_line_range": [1, 99]})
    validate_raw_input_reference("vv", {"raw_input_id": 0, "pre_text_line_range": [1, 2]})  # ok


def test_read_view_includes_numbered_pretext(monkeypatch, capsys):
    _seed_project_with_entry_and_one_quote_node("rv", "rv", monkeypatch)
    capsys.readouterr()
    rc = cli_entrypoint._handle_read(["rv", "1"])
    out = capsys.readouterr()
    payload = json.loads(out.out)  # stdout stays pure JSON
    assert "1| agent line one" in payload[0]["agent_pre_text_numbered"]
    assert payload[0]["pre_text_selection"] == "all"
    assert "pretext" in out.err  # reminder line on stderr
    assert rc == 0


def test_one_project_per_session_guard():
    add_session_to_project("proj-1", "shared-sess", "/tmp/a.jsonl")
    with pytest.raises(SessionAlreadyInDifferentProjectError):
        add_session_to_project("proj-2", "shared-sess", "/tmp/b.jsonl")
