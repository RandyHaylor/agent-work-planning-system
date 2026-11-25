"""Types of the prompt_builder module (spec: Types)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

GuidanceRole = str  # a key in data/role-presets.json: "planner", "dev_manager", "worker", "admin"


@dataclass(frozen=True)
class RoleGuidance:
    role: GuidanceRole
    template: str  # the preset name, e.g. "Planner"
    text: str  # injections for the role, then the preset's rules, ready to hand to an agent


@dataclass(frozen=True)
class EditorSession:
    url: str  # http://127.0.0.1:<port>/
    store_folder: Path  # the folder presets are saved to
