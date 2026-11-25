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


PLANNING_RULES = [("planning-references", "through-the-reader"), ("planning-claims", "claim-tags-and-citations")]


def test_worker_preset_is_careful_developer_plus_reader_and_claim_rules_without_sample_task(catalog):
    worker = catalog.find_preset("Worker")
    careful = catalog.find_preset("Careful developer")
    worker_rules = [(e["categoryId"], e["optionId"]) for e in worker["entries"]]
    careful_rules = [(e["categoryId"], e["optionId"]) for e in careful["entries"]]
    assert [r for r in worker_rules if r not in PLANNING_RULES] == careful_rules
    assert all(rule in worker_rules for rule in PLANNING_RULES)
    assert "CSV" not in ruleset.compose_prompt_text(catalog, ruleset.new_ruleset(catalog, worker))


@pytest.mark.parametrize("name", ["Planner", "Dev manager", "Worker"])
def test_planner_dev_manager_and_worker_get_the_claim_tag_rule(catalog, name):
    """Build log #50: agents must know the claim tags and citation format or their writes 422."""
    entries = [(e["categoryId"], e["optionId"], e["enabled"]) for e in catalog.find_preset(name)["entries"]]
    assert ("planning-claims", "claim-tags-and-citations", True) in entries
    text = ruleset.compose_prompt_text(catalog, ruleset.new_ruleset(catalog, catalog.find_preset(name)))
    for tag in ("requirement", "decision", "technical", "documentation", "plan", "note"):
        assert f"`{tag}`" in text
    assert "[<reference id>:<start>-<end>]" in text


def test_session_injections_are_the_repo_file_as_is():
    assert (SHIPPED_DATA_FOLDER / "session-injections.json").read_bytes() == \
        (REPO_ROOT / "agent_instruction_injections.json").read_bytes()
