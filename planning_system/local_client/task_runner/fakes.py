"""Fakes for task_runner: in-memory registry and a minimal working runner."""
from __future__ import annotations

import json
import threading
from dataclasses import replace

from planning_system.api_client import ClientSettings, PlanningApiClientInterface
from planning_system.api_client.types import ENV_CA_CERT, ENV_TOKEN, ENV_URL

from ..harness_adapters import AiCliAdapterInterface, HeadlessSessionSpec, PersistentReviewerSessionHandle
from .interface import RunningSessionsRegistryInterface, TaskRunnerInterface
from .types import RunningSession, TaskStartRequest


class InMemoryRunningSessionsRegistry(RunningSessionsRegistryInterface):

    def __init__(self):
        self._sessions: dict[str, RunningSession] = {}

    def record(self, session: RunningSession) -> None:
        self._sessions[session.agent_id] = session

    def mark_stopped(self, agent_id: str) -> None:
        self._sessions[agent_id] = replace(self._sessions[agent_id], alive=False)

    def forget(self, agent_id: str) -> None:
        self._sessions.pop(agent_id, None)

    def all(self) -> list[RunningSession]:
        return list(self._sessions.values())


class FakeTaskRunner(TaskRunnerInterface):

    def __init__(self, api: PlanningApiClientInterface, adapter: AiCliAdapterInterface, settings: ClientSettings):
        self._api = api
        self._adapter = adapter
        self._settings = settings
        self._registry = InMemoryRunningSessionsRegistry()
        self._handles: dict[str, PersistentReviewerSessionHandle] = {}

    def start_task(self, request: TaskStartRequest) -> str:
        self._api.register_agent(request.agent_id, path=str(request.working_directory))
        prompt = (self._api.guidance(request.role)["text"] + "\n\n"
                  + json.dumps(self._api.context(request.node_id), indent=2))
        environment = {ENV_URL: self._settings.base_url, ENV_TOKEN: request.token,
                       ENV_CA_CERT: str(self._settings.ca_cert_path or "")}
        handle = self._adapter.spawn_headless_session(HeadlessSessionSpec(
            request.agent_id, request.working_directory, environment, request.allowed_tools))
        threading.Thread(target=handle.send_prompt_and_await_response, args=(prompt,), daemon=True).start()
        self._handles[request.agent_id] = handle
        self._registry.record(RunningSession(request.agent_id, request.node_id, request.role,
                                             str(request.working_directory)))
        return handle.session_id

    def stop_task(self, agent_id: str) -> None:
        self._handles[agent_id].terminate()
        self._registry.mark_stopped(agent_id)

    def running_tasks(self) -> list[RunningSession]:
        return self._registry.all()
