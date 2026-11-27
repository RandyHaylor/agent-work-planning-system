"""PARKED (user 2026-11-26): pinned, not wired; may be integrated later the way Unharness does. Not selectable
from ReviewerBackendFactory; kept with its tests (run against a fake pi process).

pi: our tiny pi harness (build log #47): the npm-installed pi CLI under tools/pi in RPC mode, isolated config
via PI_CODING_AGENT_DIR=tools/pi/agent, provider local-llamacpp (the same llama.cpp gemma4 server), thinking off
through PI_REQUEST_PAYLOAD_INJECTION_JSON (read by the copied reasoning-control extension). Bare: no tools, no
session file, no context files/skills/templates/themes. Running it live waits on the user's OK (build log #48)."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Mapping, Optional, Sequence

from ..review_conversation import ReviewConversation
from .conversational_backend import ConversationalReviewerBackend
from .conversations import TranscriptReplayConversation
from .pi_rpc_exchange import run_pi_prompt

DEFAULT_PI_MODEL = "gemma4-31b-jang-q3:latest"
PI_PROVIDER = "local-llamacpp"
PI_CLI_RELATIVE_PATH = "node_modules/@earendil-works/pi-coding-agent/dist/cli.js"
PI_DIRECTORY_ENVIRONMENT_VARIABLE = "PLANNING_PI_DIR"
THINKING_OFF_PAYLOAD = {"chat_template_kwargs": {"enable_thinking": False}}


def default_pi_directory() -> Path:
    """$PLANNING_PI_DIR, else <repo>/tools/pi."""
    configured = os.environ.get(PI_DIRECTORY_ENVIRONMENT_VARIABLE)
    return Path(configured) if configured else Path(__file__).resolve().parents[4] / "tools" / "pi"


class PiBackend(ConversationalReviewerBackend):
    name = "pi"

    def __init__(self, model: str = DEFAULT_PI_MODEL, pi_directory: Optional[Path] = None,
                 command: Optional[Sequence[str]] = None, timeout_seconds: float = 180.0,
                 extra_environment: Optional[Mapping[str, str]] = None):
        self._model = model
        self._pi_directory = Path(pi_directory) if pi_directory is not None else default_pi_directory()
        self._command = list(command) if command is not None else None
        self._timeout = timeout_seconds
        self._extra_environment = dict(extra_environment or {})

    @property
    def launch_command(self) -> list[str]:
        if self._command is not None:
            return list(self._command)
        return ["node", str(self._pi_directory / PI_CLI_RELATIVE_PATH), "--mode", "rpc",
                "--provider", PI_PROVIDER, "--model", self._model,
                "--no-session", "--no-tools", "--no-context-files", "--no-skills", "--no-prompt-templates",
                "--no-themes"]

    @property
    def launch_environment(self) -> dict[str, str]:
        return {**os.environ,
                "PI_CODING_AGENT_DIR": str(self._pi_directory / "agent"),
                "PI_REQUEST_PAYLOAD_INJECTION_JSON": json.dumps(THINKING_OFF_PAYLOAD),
                **self._extra_environment}

    def _open_conversation(self) -> ReviewConversation:
        return TranscriptReplayConversation(self._ask)    # one pi process per turn (--no-session)

    def _ask(self, prompt: str) -> str:
        return run_pi_prompt(self.launch_command, self.launch_environment, prompt, self._timeout)
