"""role_guidance: role -> preset -> composed guidance text, using the copied tool's own compose code.

Files are re-read on every call so edits made on the website show at once (no restart).
"""
from __future__ import annotations

from pathlib import Path

from planning_system.contract import NotFound
from planning_system.prompt_builder.ai_prompt_builder import ruleset
from planning_system.prompt_builder.ai_prompt_builder.rule_catalog import RuleCatalog, SHIPPED_DATA_FOLDER, read_json
from planning_system.prompt_builder.guidance_interface import GuidanceService
from planning_system.prompt_builder.guidance_types import GuidanceRole, RoleGuidance

ROLE_PRESETS_FILE = SHIPPED_DATA_FOLDER / "role-presets.json"
SESSION_INJECTIONS_FILE = SHIPPED_DATA_FOLDER / "session-injections.json"
BLOCK_SEPARATOR = "\n\n"


class RolePresetMap:
    """Reads data/role-presets.json; role name -> preset name."""

    def __init__(self, path: Path = ROLE_PRESETS_FILE):
        self.path = Path(path)

    def preset_name_for(self, role: GuidanceRole) -> str:  # raises NotFound for an unknown role
        roles = self.roles()
        if role not in roles:
            raise NotFound(f"no guidance role '{role}'")
        return roles[role]

    def roles(self) -> dict[GuidanceRole, str]:
        return dict(read_json(self.path)["rolePresets"])


class SessionInjections:
    """Reads data/session-injections.json; texts whose applies_to lists the role."""

    def __init__(self, path: Path = SESSION_INJECTIONS_FILE):
        self.path = Path(path)

    def blocks_for(self, role: GuidanceRole) -> list[str]:
        return [item["text"] for item in read_json(self.path)["injections"] if role in item["applies_to"]]


class GuidanceComposer(GuidanceService):
    """Injections for the role, then catalog.find_preset -> new_ruleset -> compose_prompt_text."""

    def __init__(self, catalog: RuleCatalog, role_map: RolePresetMap, injections: SessionInjections):
        self.catalog = catalog
        self.role_map = role_map
        self.injections = injections

    def _fresh_catalog(self) -> RuleCatalog:
        return RuleCatalog(user_folder=self.catalog.user_folder)

    def guidance_for(self, role: GuidanceRole) -> RoleGuidance:
        preset_name = self.role_map.preset_name_for(role)
        catalog = self._fresh_catalog()
        preset = catalog.find_preset(preset_name)
        if preset is None:
            raise NotFound(f"no preset '{preset_name}' for role '{role}'")
        rules_text = ruleset.compose_prompt_text(catalog, ruleset.new_ruleset(catalog, preset))
        blocks = self.injections.blocks_for(role) + [rules_text]
        return RoleGuidance(role=role, template=preset["name"], text=BLOCK_SEPARATOR.join(blocks))

    def templates(self) -> dict:
        return {"rolePresets": self.role_map.roles(), "presets": self._fresh_catalog().list_presets()}

    def rules(self) -> list:
        return self._fresh_catalog().list_categories()
