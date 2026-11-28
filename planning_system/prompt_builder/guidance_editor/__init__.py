"""guidance_editor: starts the copied local web server on the server's preset folder."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..ai_prompt_builder.local_web_server import RuleBuilderSession, start_server
from ..ai_prompt_builder.rule_catalog import RuleCatalog
from ..guidance_interface import GuidanceEditorLauncher
from ..guidance_types import EditorSession


class GuidanceEditor(GuidanceEditorLauncher):
    """The website serves on its own thread; shutdown() stops it."""

    def __init__(self, store_folder: Path):
        self.store_folder = Path(store_folder)
        self._server: Optional[object] = None

    def launch(self) -> EditorSession:
        self._server = start_server(RuleBuilderSession(RuleCatalog(user_folder=self.store_folder), None, None))
        return EditorSession(url=f"http://127.0.0.1:{self._server.server_address[1]}/",
                             store_folder=self.store_folder)

    def shutdown(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
