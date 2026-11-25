"""The shipped data (spec test 9 plus build log #21/#22): runs for real now."""
from __future__ import annotations

import json

import pytest

from planning_system.prompt_builder.ai_prompt_builder import ruleset
from planning_system.prompt_builder.ai_prompt_builder.rule_catalog import RuleCatalog, SHIPPED_DATA_FOLDER

REPO_ROOT = SHIPPED_DATA_FOLDER.parents[2]


@pytest.fixture
def catalog(tmp_path):
    return RuleCatalog(user_folder=tmp_path / "empty")


def preset_names():
    index = json.loads((SHIPPED_DATA_FOLDER / "presets" / "index.json").read_text())
    return [json.loads((SHIPPED_DATA_FOLDER / "presets" / f).read_text())["name"] for f in index["presetFiles"]]


def test_category_ids_are_unique(catalog):
    ids = [c["categoryId"] for c in catalog.shipped_categories]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("name", preset_names())
def test_preset_references_only_existing_rules_and_composes(catalog, name):
    preset = catalog.find_preset(name)
    for entry in preset["entries"]:
        assert catalog.find_option(entry["categoryId"], entry["optionId"]), (name, entry)
    built = ruleset.new_ruleset(catalog, preset)
    assert built["rulesNotFound"] == []
    assert ruleset.compose_prompt_text(catalog, built).strip()


def test_every_role_maps_to_an_existing_preset(catalog):
    roles = json.loads((SHIPPED_DATA_FOLDER / "role-presets.json").read_text())["rolePresets"]
    assert set(roles) == {"planner", "dev_manager", "worker", "admin"}
    for preset_name in roles.values():
        assert catalog.find_preset(preset_name) is not None, preset_name


def test_worker_preset_is_careful_developer_plus_reader_rule_without_sample_task(catalog):
    worker = catalog.find_preset("Worker")
    careful = catalog.find_preset("Careful developer")
    worker_rules = [(e["categoryId"], e["optionId"]) for e in worker["entries"]]
    careful_rules = [(e["categoryId"], e["optionId"]) for e in careful["entries"]]
    assert [r for r in worker_rules if r != ("planning-references", "through-the-reader")] == careful_rules
    assert ("planning-references", "through-the-reader") in worker_rules
    assert "CSV" not in ruleset.compose_prompt_text(catalog, ruleset.new_ruleset(catalog, worker))


def test_session_injections_are_the_repo_file_as_is():
    assert (SHIPPED_DATA_FOLDER / "session-injections.json").read_bytes() == \
        (REPO_ROOT / "agent_instruction_injections.json").read_bytes()
