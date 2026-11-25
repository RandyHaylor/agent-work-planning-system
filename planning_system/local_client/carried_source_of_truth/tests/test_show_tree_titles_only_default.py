"""T10: show-tree default = compact `<id> <title>` (no brackets); --show-all uses inlined-quote view."""
from __future__ import annotations

import json

from source_of_truth.cli_entrypoint import _handle_show_tree, _handle_submit_change_set
from source_of_truth.compact_tree_renderer import (
    render_tree_titles_only_indented,
    render_tree_compact,
)
from source_of_truth.load_config import (
    ProjectSettings,
    REVIEWER_MODE_NO_REVIEWER_DIRECT_APPLY,
    save_project_settings,
)
from source_of_truth.raw_input_log_writer import append_submission_to_raw_input_log
from source_of_truth.requirements_tree_node_schema import (
    GROUP_NODE_KIND,
    QUOTE_REFERENCE_NODE_KIND,
    RawInputReference,
    RequirementsTree,
    RequirementsTreeNode,
)


def _build_tiny_tree_with_one_top_group_one_top_leaf_and_one_nested_leaf() -> RequirementsTree:
    tree = RequirementsTree(project_id="p", next_node_id=3, next_group_letter_index=1)
    tree.nodes_by_id["a"] = RequirementsTreeNode(
        node_id="a", parent_id="0", kind=GROUP_NODE_KIND,
        short_neutral_title="vendor rules", child_node_ids=["1"],
    )
    tree.nodes_by_id["1"] = RequirementsTreeNode(
        node_id="1", parent_id="a", kind=QUOTE_REFERENCE_NODE_KIND,
        raw_input_reference=RawInputReference(raw_input_id=42),
        short_neutral_title="vendor placement",
    )
    tree.nodes_by_id["2"] = RequirementsTreeNode(
        node_id="2", parent_id="0", kind=QUOTE_REFERENCE_NODE_KIND,
        raw_input_reference=RawInputReference(raw_input_id=43),
        short_neutral_title="back end stack",
    )
    return tree


def test_titles_only_renderer_emits_id_space_title_with_no_brackets():
    tree = _build_tiny_tree_with_one_top_group_one_top_leaf_and_one_nested_leaf()
    output = render_tree_titles_only_indented("p", tree)
    lines = output.splitlines()
    # First (header) line is informational; subsequent lines are nodes.
    body_lines = [ln for ln in lines if ln.startswith(" ") or ln[:1].isalnum()]
    # No brackets allowed in any rendered line.
    for line in lines:
        assert "[" not in line and "]" not in line, f"unexpected brackets in: {line!r}"
    # Each top-level group/leaf appears with id+title.
    assert any(ln.lstrip().startswith("nd-a vendor rules") for ln in lines)
    assert any(ln.lstrip().startswith("nd-2 back end stack") for ln in lines)
    # Nested leaf indented (two spaces beyond its parent).
    assert any(ln.startswith("  nd-1 vendor placement") for ln in lines)


def test_show_tree_default_uses_titles_only_renderer(capsys):
    save_project_settings(ProjectSettings(
        project_id="p-titles", reviewer_mode_override=REVIEWER_MODE_NO_REVIEWER_DIRECT_APPLY,
    ))
    log_result = append_submission_to_raw_input_log("p-titles", "s", "raw text body", "")
    _handle_submit_change_set([
        "p-titles", "--add", str(log_result["raw_input_id"]),
        "--parent", "0", "--title", "back end stack",
    ])
    capsys.readouterr()
    rc = _handle_show_tree(["p-titles"])
    captured = capsys.readouterr()
    assert rc == 0
    assert "nd-1 back end stack" in captured.out
    # Default must NOT inline the raw quote text.
    assert "raw text body" not in captured.out
    assert "[" not in captured.out and "]" not in captured.out


def test_show_tree_show_all_flag_inlines_quote_text(capsys):
    save_project_settings(ProjectSettings(
        project_id="p-showall", reviewer_mode_override=REVIEWER_MODE_NO_REVIEWER_DIRECT_APPLY,
    ))
    log_result = append_submission_to_raw_input_log("p-showall", "s", "this raw quote should show", "")
    _handle_submit_change_set([
        "p-showall", "--add", str(log_result["raw_input_id"]),
        "--parent", "0", "--title", "tconfig",
    ])
    capsys.readouterr()
    rc = _handle_show_tree(["p-showall", "--show-all"])
    captured = capsys.readouterr()
    assert rc == 0
    assert "this raw quote should show" in captured.out
