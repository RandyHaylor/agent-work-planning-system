"""T2: GROUP_NODE_KIND round-trips through JSON; no raw_input_reference, no project_paths."""
from source_of_truth.requirements_tree_node_schema import (
    GROUP_NODE_KIND,
    RequirementsTreeNode,
)


def test_group_node_round_trips_with_title_and_no_quote_or_paths():
    original = RequirementsTreeNode(
        node_id=1,
        parent_id=None,
        kind=GROUP_NODE_KIND,
        short_neutral_title="vendor placement rules",
        child_node_ids=[],
    )
    round_tripped = RequirementsTreeNode.from_json_dict(original.to_json_dict())
    assert round_tripped.kind == GROUP_NODE_KIND
    assert round_tripped.short_neutral_title == "vendor placement rules"
    assert round_tripped.raw_input_reference is None
    assert round_tripped.project_paths == []
