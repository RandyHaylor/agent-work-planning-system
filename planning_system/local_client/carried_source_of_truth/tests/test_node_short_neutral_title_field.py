"""T1: short_neutral_title field round-trips through JSON; legacy nodes load with empty string."""
from source_of_truth.requirements_tree_node_schema import (
    QUOTE_REFERENCE_NODE_KIND,
    RawInputReference,
    RequirementsTreeNode,
)


def test_node_with_explicit_title_round_trips_through_json():
    original = RequirementsTreeNode(
        node_id=1,
        parent_id=None,
        kind=QUOTE_REFERENCE_NODE_KIND,
        raw_input_reference=RawInputReference(raw_input_id=42),
        short_neutral_title="vendor placement",
    )
    round_tripped = RequirementsTreeNode.from_json_dict(original.to_json_dict())
    assert round_tripped.short_neutral_title == "vendor placement"


def test_legacy_node_without_title_loads_with_empty_string():
    legacy_payload_missing_title_field = {
        "node_id": 99,
        "parent_id": None,
        "kind": QUOTE_REFERENCE_NODE_KIND,
        "child_node_ids": [],
        "raw_input_reference": {"raw_input_id": 7},
    }
    loaded = RequirementsTreeNode.from_json_dict(legacy_payload_missing_title_field)
    assert loaded.short_neutral_title == ""
