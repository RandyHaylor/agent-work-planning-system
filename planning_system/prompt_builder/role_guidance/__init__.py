"""role_guidance: role -> preset -> composed guidance text. Hollow until level 7."""
from __future__ import annotations

from pathlib import Path

from planning_system.prompt_builder.ai_prompt_builder.rule_catalog import RuleCatalog, SHIPPED_DATA_FOLDER
from planning_system.prompt_builder.guidance_interface import GuidanceService
from planning_system.prompt_builder.guidance_types import GuidanceRole, RoleGuidance

ROLE_PRESETS_FILE = SHIPPED_DATA_FOLDER / "role-presets.json"
SESSION_INJECTIONS_FILE = SHIPPED_DATA_FOLDER / "session-injections.json"


class RolePresetMap:
    """Reads data/role-presets.json; role name -> preset name."""

    def __init__(self, path: Path = ROLE_PRESETS_FILE):
        self.path = path

    def preset_name_for(self, role: GuidanceRole) -> str:  # raises NotFound for an unknown role
        raise NotImplementedError

    def roles(self) -> dict[GuidanceRole, str]:
        raise NotImplementedError


class SessionInjections:
    """Reads data/session-injections.json; texts whose applies_to lists the role."""

    def __init__(self, path: Path = SESSION_INJECTIONS_FILE):
        self.path = path

    def blocks_for(self, role: GuidanceRole) -> list[str]:
        raise NotImplementedError


class GuidanceComposer(GuidanceService):
    """Injections for the role, then catalog.find_preset -> new_ruleset -> compose_prompt_text."""

    def __init__(self, catalog: RuleCatalog, role_map: RolePresetMap, injections: SessionInjections):
        self.catalog = catalog
        self.role_map = role_map
        self.injections = injections

    def guidance_for(self, role: GuidanceRole) -> RoleGuidance:
        raise NotImplementedError

    def templates(self) -> dict:
        raise NotImplementedError

    def rules(self) -> list:
        raise NotImplementedError
