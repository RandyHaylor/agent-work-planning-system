"""Fakes of the prompt_builder interfaces (build log #11). Consumers test against these.

The fake guidance service takes its role map and injections in memory and composes with
the copied tool's catalog, so it behaves like the real one without the file readers.
"""
from __future__ import annotations

from pathlib import Path

from planning_system.contract import NotFound
from planning_system.prompt_builder.ai_prompt_builder import ruleset
from planning_system.prompt_builder.ai_prompt_builder.local_web_server import RuleBuilderSession, start_server
from planning_system.prompt_builder.ai_prompt_builder.rule_catalog import RuleCatalog
from planning_system.prompt_builder.guidance_interface import GuidanceEditorLauncher, GuidanceService
from planning_system.prompt_builder.guidance_types import EditorSession, GuidanceRole, RoleGuidance


class FakeGuidanceService(GuidanceService):
    def __init__(self, preset_folder: Path, role_presets: dict[str, str], injections: list[dict]):
        self.preset_folder = Path(preset_folder)
        self.role_presets = dict(role_presets)
        self.injections = list(injections)  # [{"applies_to": [...], "text": "..."}]

    def _catalog(self) -> RuleCatalog:
        return RuleCatalog(user_folder=self.preset_folder)

    def guidance_for(self, role: GuidanceRole) -> RoleGuidance:
        if role not in self.role_presets:
            raise NotFound(f"no guidance role '{role}'")
        catalog = self._catalog()
        preset = catalog.find_preset(self.role_presets[role])
        if preset is None:
            raise NotFound(f"no preset '{self.role_presets[role]}'")
        rules_text = ruleset.compose_prompt_text(catalog, ruleset.new_ruleset(catalog, preset))
        blocks = [i["text"] for i in self.injections if role in i["applies_to"]]
        return RoleGuidance(role=role, template=preset["name"], text="\n\n".join(blocks + [rules_text]))

    def templates(self) -> dict:
        return {"rolePresets": dict(self.role_presets), "presets": self._catalog().list_presets()}

    def rules(self) -> list:
        return self._catalog().list_categories()


class FakeGuidanceEditor(GuidanceEditorLauncher):
    """Starts the copied server for real (it serves on its own thread); call shutdown() when done."""

    def __init__(self, store_folder: Path):
        self.store_folder = Path(store_folder)
        self.server = None

    def launch(self) -> EditorSession:
        self.server = start_server(RuleBuilderSession(RuleCatalog(user_folder=self.store_folder), None, None))
        return EditorSession(url=f"http://127.0.0.1:{self.server.server_address[1]}/", store_folder=self.store_folder)

    def shutdown(self) -> None:
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
