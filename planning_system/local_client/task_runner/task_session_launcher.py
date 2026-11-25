"""task_session_launcher: TaskStartRequest -> start prompt (guidance + context via api_client) -> adapter session.

Level 6 scaffold: hollow.
"""
from __future__ import annotations

from planning_system.api_client import ClientSettings, PlanningApiClientInterface

from ..harness_adapters import AiCliAdapterInterface, PersistentReviewerSessionHandle
from .types import TaskStartRequest


class TaskSessionLauncher:

    def __init__(self, api: PlanningApiClientInterface, adapter: AiCliAdapterInterface,
                 settings: ClientSettings):
        self._api = api
        self._adapter = adapter
        self._settings = settings

    def launch(self, request: TaskStartRequest) -> PersistentReviewerSessionHandle:
        """Spawns the session and sends the start prompt in the background; returns at once."""
        raise NotImplementedError("level 7")
