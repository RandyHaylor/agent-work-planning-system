"""Abstract interfaces of the prompt_builder module (build log #11: ABC, fake, hollow real)."""
from __future__ import annotations

from abc import ABC, abstractmethod

from .guidance_types import EditorSession, GuidanceRole, RoleGuidance


class GuidanceService(ABC):
    """What the /guidance routes read. The catalog is re-read per call so website edits show at once."""

    @abstractmethod
    def guidance_for(self, role: GuidanceRole) -> RoleGuidance:
        """Injections for the role, then the role's preset composed. Raises NotFound for an unknown role."""

    @abstractmethod
    def templates(self) -> dict:
        """{"rolePresets": {role: preset name}, "presets": [every preset, shipped and user]}."""

    @abstractmethod
    def rules(self) -> list:
        """Every category with its options."""


class GuidanceEditorLauncher(ABC):
    """Starts the copied website on the server's preset folder."""

    @abstractmethod
    def launch(self) -> EditorSession: ...
