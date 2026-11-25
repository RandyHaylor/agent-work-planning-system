"""New projects are pre-seeded with default top-level subject groups."""
from __future__ import annotations

from source_of_truth import cli_entrypoint
from source_of_truth.requirements_tree_node_schema import (
    DEFAULT_PROJECT_SCAFFOLD_GROUP_TITLES,
    GROUP_NODE_KIND,
    RequirementsTree,
)
from source_of_truth.requirements_tree_store import load_requirements_tree


def test_scaffolded_tree_has_default_groups_as_text_less_categories():
    tree = RequirementsTree.scaffolded_for_new_project("p-scaffold")
    top_ids = tree.list_top_level_node_ids()
    assert top_ids == ["a", "b", "c", "d", "e", "f", "g"]
    assert [tree.nodes_by_id[nid].short_neutral_title for nid in top_ids] == list(
        DEFAULT_PROJECT_SCAFFOLD_GROUP_TITLES
    )
    for nid in top_ids:
        node = tree.nodes_by_id[nid]
        assert node.kind == GROUP_NODE_KIND
        assert node.raw_input_reference is None  # text-less category, no quote
    assert "resources" in tree.nodes_by_id["a"].short_neutral_title


def test_init_and_register_persists_scaffolded_groups():
    rc = cli_entrypoint._handle_init_and_register(["sess-scaf", "/tmp/s.jsonl"])
    assert rc == 0
    tree = load_requirements_tree("sess-scaf")
    titles = [tree.nodes_by_id[nid].short_neutral_title for nid in tree.list_top_level_node_ids()]
    for expected_title in DEFAULT_PROJECT_SCAFFOLD_GROUP_TITLES:
        assert expected_title in titles
