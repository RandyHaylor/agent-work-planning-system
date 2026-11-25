"""Contract tests for prompt_builder (spec 05-spec-prompt-builder.md, external integration
tests 1-7, 9), run against the fake and the real implementation (build log #11)."""
from __future__ import annotations

import json
import urllib.request

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from planning_system.contract import Principal
from planning_system.prompt_builder import http_routes
from planning_system.prompt_builder.ai_prompt_builder import ruleset
from planning_system.prompt_builder.ai_prompt_builder.rule_catalog import RuleCatalog, SHIPPED_DATA_FOLDER
from planning_system.prompt_builder.fakes import FakeGuidanceEditor, FakeGuidanceService
from planning_system.prompt_builder.guidance_editor import GuidanceEditor
from planning_system.prompt_builder.role_guidance import GuidanceComposer, RolePresetMap, SessionInjections
from planning_system.server.http_api.dependencies import current_principal

LEVEL_7 = pytest.mark.xfail(strict=False, reason="level 7")
ROLE_PRESETS = json.loads((SHIPPED_DATA_FOLDER / "role-presets.json").read_text())["rolePresets"]
INJECTIONS = json.loads((SHIPPED_DATA_FOLDER / "session-injections.json").read_text())["injections"]


def make_fake_service(folder):
    return FakeGuidanceService(folder, ROLE_PRESETS, INJECTIONS)


def make_real_service(folder):
    return GuidanceComposer(RuleCatalog(user_folder=folder), RolePresetMap(), SessionInjections())


SERVICES = [pytest.param(make_fake_service, id="fake"),
            pytest.param(make_real_service, id="real", marks=LEVEL_7)]
EDITORS = [pytest.param(FakeGuidanceEditor, id="fake"),
           pytest.param(GuidanceEditor, id="real", marks=LEVEL_7)]


@pytest.fixture
def preset_folder(tmp_path):
    return tmp_path / "prompt_builder"


@pytest.fixture(params=SERVICES)
def client(request, preset_folder):
    service = request.param(preset_folder)
    app = FastAPI()
    app.include_router(http_routes.router)
    app.dependency_overrides[current_principal] = lambda: Principal(agent_id="a1", role="planner")
    app.dependency_overrides[http_routes.guidance_service] = lambda: service
    return TestClient(app)


def composed(preset_name: str) -> str:
    catalog = RuleCatalog(user_folder=SHIPPED_DATA_FOLDER / "_unused")
    return ruleset.compose_prompt_text(catalog, ruleset.new_ruleset(catalog, catalog.find_preset(preset_name)))


def injections_for(role: str) -> list[str]:
    return [i["text"] for i in INJECTIONS if role in i["applies_to"]]


def test_1_worker_gets_worker_preset_after_its_injections(client):
    body = client.get("/guidance/worker").json()
    assert body["role"] == "worker"
    assert body["template"] == "Worker"  # build log #21 (spec said "Careful developer")
    assert body["text"] == "\n\n".join(injections_for("worker") + [composed("Worker")])
    assert "CSV" not in body["text"]


def test_2_planner_has_process_rules_and_dev_manager_rules(client):
    body = client.get("/guidance/planner").json()
    assert body["template"] == "Planner"
    catalog = RuleCatalog(user_folder=SHIPPED_DATA_FOLDER / "_unused")
    for category_id in ("planning-process-levels", "planning-level-5", "planning-module-design",
                        "planning-asking-the-user", "planning-approval", "planning-running-tasks",
                        "planning-references"):
        assert f"## {catalog.find_category(category_id)['categoryName']}" in body["text"]
    assert composed("Planner") in body["text"]


def test_3_dev_manager_is_planner_rules_with_dev_manager_text_first(client):
    body = client.get("/guidance/dev_manager").json()
    dev_manager_text = RuleCatalog(user_folder=SHIPPED_DATA_FOLDER / "_unused").find_preset(
        "Dev manager")["customText"]["text"]
    planner_rules = composed("Planner")
    assert body["text"].index(dev_manager_text) < body["text"].index(planner_rules)


def test_4_unknown_role_is_404(client):
    assert client.get("/guidance/nobody").status_code == 404


def test_5_user_preset_mapped_to_role_is_served_without_restart(preset_folder):
    # Needs a role map pointing at a user preset; the fake takes its map in memory.
    catalog = RuleCatalog(user_folder=preset_folder)
    catalog.save_user_preset({"entries": [], "customText": {"text": "my own rules", "placement": "end",
                                                            "enabled": True}}, "Mine")
    service = FakeGuidanceService(preset_folder, {"worker": "Mine"}, [])
    assert service.guidance_for("worker").text == "my own rules"


@pytest.mark.xfail(strict=False, reason="level 7")
def test_5_real_user_preset_mapped_to_role_is_served_without_restart(preset_folder, tmp_path):
    role_map_file = tmp_path / "role-presets.json"
    role_map_file.write_text(json.dumps({"rolePresets": {"worker": "Mine"}}))
    service = GuidanceComposer(RuleCatalog(user_folder=preset_folder), RolePresetMap(role_map_file),
                               SessionInjections())
    RuleCatalog(user_folder=preset_folder).save_user_preset(
        {"entries": [], "customText": {"text": "my own rules", "placement": "end", "enabled": True}}, "Mine")
    assert service.guidance_for("worker").text.endswith("my own rules")


def test_templates_and_rules_routes(client):
    templates = client.get("/guidance/templates").json()
    assert templates["rolePresets"] == ROLE_PRESETS
    assert {"Planner", "Dev manager", "Worker"} <= {p["name"] for p in templates["presets"]}
    rules = client.get("/guidance/rules").json()
    assert any(c["categoryId"] == "planning-process-levels" for c in rules)


@pytest.fixture(params=EDITORS)
def editor_session(request, preset_folder):
    editor = request.param(preset_folder)
    session = editor.launch()
    yield session
    if hasattr(editor, "shutdown"):
        editor.shutdown()


def test_6_website_saves_into_preset_folder_not_data(editor_session, preset_folder):
    data_before = sorted(p.name for p in (SHIPPED_DATA_FOLDER / "presets").iterdir())
    body = json.dumps({"customCategories": [], "customOptions": [], "customPresets": [
        {"presetName": "Mine", "entries": [], "customText": {"text": "x", "placement": "end", "enabled": True}}]})
    request = urllib.request.Request(editor_session.url + "api/customizations", data=body.encode(),
                                     method="PUT", headers={"Content-Type": "application/json"})
    urllib.request.urlopen(request).read()
    assert (preset_folder / "customizations.json").exists()
    assert sorted(p.name for p in (SHIPPED_DATA_FOLDER / "presets").iterdir()) == data_before


def test_7_launch_serves_index_and_session_settings(editor_session, preset_folder):
    assert editor_session.url.startswith("http://127.0.0.1:")
    assert editor_session.store_folder == preset_folder
    assert b"<html" in urllib.request.urlopen(editor_session.url).read().lower()
    settings = json.loads(urllib.request.urlopen(editor_session.url + "api/session-settings").read())
    assert settings["storeFolder"] == str(preset_folder)
