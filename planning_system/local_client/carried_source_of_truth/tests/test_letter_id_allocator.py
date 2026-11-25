"""T3: letter_id_for_index — Excel-column-style base-26 (no zero digit)."""
import pytest

from source_of_truth.requirements_tree_node_schema import letter_id_for_index


def test_first_26_indices_map_to_single_lowercase_letters():
    assert letter_id_for_index(0) == "a"
    assert letter_id_for_index(1) == "b"
    assert letter_id_for_index(25) == "z"


def test_index_26_rolls_over_to_double_letter_aa():
    assert letter_id_for_index(26) == "aa"


def test_indices_after_first_double_letter_progress_correctly():
    assert letter_id_for_index(27) == "ab"
    assert letter_id_for_index(51) == "az"
    assert letter_id_for_index(52) == "ba"


def test_zz_is_index_701_and_aaa_is_index_702():
    assert letter_id_for_index(701) == "zz"
    assert letter_id_for_index(702) == "aaa"


def test_negative_index_raises_value_error():
    with pytest.raises(ValueError):
        letter_id_for_index(-1)


def test_tree_persists_next_group_letter_index_through_round_trip():
    from source_of_truth.requirements_tree_node_schema import RequirementsTree
    tree = RequirementsTree(project_id="p", next_node_id=1, next_group_letter_index=5)
    round_tripped = RequirementsTree.from_json_dict(tree.to_json_dict())
    assert round_tripped.next_group_letter_index == 5


def test_legacy_tree_without_letter_index_field_loads_with_zero():
    from source_of_truth.requirements_tree_node_schema import RequirementsTree
    legacy_payload = {"project_id": "p", "next_node_id": 1}
    loaded = RequirementsTree.from_json_dict(legacy_payload)
    assert loaded.next_group_letter_index == 0
