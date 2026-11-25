"""read / search-nodes show the resolved quote text (not just a pointer), and
--show-all renders group/quote titles instead of the bare kind."""
from __future__ import annotations

import json

from source_of_truth import cli_entrypoint
from source_of_truth.add_session_to_project_cli import add_session_to_project
from source_of_truth.compact_tree_renderer import render_tree_compact
from source_of_truth.raw_input_log_writer import append_submission_to_raw_input_log
from source_of_truth.requirements_tree_node_schema import (
    QUOTE_REFERENCE_NODE_KIND,
    RawInputReference,
    RequirementsTree,
    RequirementsTreeNode,
)
from source_of_truth.requirements_tree_store import save_requirements_tree_atomically


def _seed(project_id, session_id):
    add_session_to_project(project_id, session_id, "/tmp/s.jsonl")
    append_submission_to_raw_input_log(
        project_id, session_id, "must support offline mode for 24h", "agent line\nsecond line"
    )
    node = RequirementsTreeNode(
        node_id="1", parent_id="0", kind=QUOTE_REFERENCE_NODE_KIND,
        raw_input_reference=RawInputReference(raw_input_id=0), short_neutral_title="offline mode",
    )
    tree = RequirementsTree(project_id=project_id, next_node_id=2, nodes_by_id={"1": node})
    save_requirements_tree_atomically(tree)


def test_read_shows_resolved_quote_text(capsys):
    _seed("pr", "pr")
    capsys.readouterr()
    cli_entrypoint._handle_read(["pr", "1"])
    payload = json.loads(capsys.readouterr().out)
    assert "must support offline mode for 24h" in payload[0]["cited_text"]


def test_search_match_includes_quote_text(capsys):
    _seed("ps", "ps")
    capsys.readouterr()
    cli_entrypoint._handle_search_nodes(["ps", "offline mode for 24h"])
    out = json.loads(capsys.readouterr().out)
    assert out["matches"], "expected a match"
    assert "must support offline mode for 24h" in out["matches"][0]["cited_text"]


def test_show_all_renders_group_titles_not_bare_kind():
    tree = RequirementsTree.scaffolded_for_new_project("pg")
    rendered = render_tree_compact("pg", tree)
    assert "resources" in rendered
    assert "technical-requirements" in rendered
    assert "] group" not in rendered  # no bare-kind group lines
