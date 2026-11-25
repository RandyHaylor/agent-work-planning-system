"""guidance_editor: starts the copied local web server on the server's preset folder. Hollow until level 7."""
from __future__ import annotations

from pathlib import Path

from planning_system.prompt_builder.guidance_interface import GuidanceEditorLauncher
from planning_system.prompt_builder.guidance_types import EditorSession


class GuidanceEditor(GuidanceEditorLauncher):
    def __init__(self, store_folder: Path):
        self.store_folder = Path(store_folder)

    def launch(self) -> EditorSession:
        # local_web_server.start_server(RuleBuilderSession(RuleCatalog(store_folder), None, None))
        raise NotImplementedError
