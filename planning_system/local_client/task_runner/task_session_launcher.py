"""task_session_launcher: TaskStartRequest -> start prompt (guidance + context via api_client) -> adapter session."""
from __future__ import annotations

import json
import threading
import time

from planning_system.api_client import ClientSettings, PlanningApiClientInterface
from planning_system.api_client.types import ENV_CA_CERT, ENV_TOKEN, ENV_URL

from ..harness_adapters import AiCliAdapterInterface, HeadlessSessionSpec, PersistentReviewerSessionHandle
from .types import TaskStartRequest

PROMPT_HANDOFF_WAIT_SECONDS = 10.0


class TaskSessionLauncher:

    def __init__(self, api: PlanningApiClientInterface, adapter: AiCliAdapterInterface,
                 settings: ClientSettings):
        self._api = api
        self._adapter = adapter
        self._settings = settings

    def launch(self, request: TaskStartRequest) -> PersistentReviewerSessionHandle:
        """Registers the agent, spawns the session and sends the start prompt in the background; returns once
        the prompt has been handed over (not when the session finishes)."""
        self._api.register_agent(request.agent_id, path=str(request.working_directory))
        prompt = self._start_prompt(request)
        handle = self._adapter.spawn_headless_session(HeadlessSessionSpec(
            request.agent_id, request.working_directory, self._session_environment(request),
            request.allowed_tools, model=request.model))
        threading.Thread(target=handle.send_prompt_and_await_response, args=(prompt,), daemon=True).start()
        self._wait_for_prompt_handoff(handle)
        return handle

    def _start_prompt(self, request: TaskStartRequest) -> str:
        guidance = self._api.guidance(request.role)["text"]
        context = self._api.context(request.node_id)
        return f"{guidance}\n\n{json.dumps(context, indent=2)}"

    def _session_environment(self, request: TaskStartRequest) -> dict[str, str]:
        """The task token goes only here, never into the prompt."""
        return {ENV_URL: self._settings.base_url, ENV_TOKEN: request.token,
                ENV_CA_CERT: str(self._settings.ca_cert_path or "")}

    @staticmethod
    def _wait_for_prompt_handoff(handle: PersistentReviewerSessionHandle) -> None:
        """Handles that run a real process expose `pid` once the prompt is written; wait for it so the caller
        (often a short-lived `planning` command) does not exit first. Other handles return at once."""
        if not hasattr(handle, "pid"):
            return
        deadline = time.monotonic() + PROMPT_HANDOFF_WAIT_SECONDS
        while handle.pid is None and time.monotonic() < deadline:
            time.sleep(0.05)
