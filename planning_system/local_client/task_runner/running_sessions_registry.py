"""running_sessions_registry: local JSON file of sessions this client started."""
from __future__ import annotations

import json
import os
from dataclasses import asdict, replace
from pathlib import Path

from .interface import RunningSessionsRegistryInterface
from .types import RunningSession


class RunningSessionsRegistry(RunningSessionsRegistryInterface):
    """{agent_id: RunningSession fields}, rewritten atomically on each change."""

    def __init__(self, registry_file: Path):
        self._registry_file = Path(registry_file)

    def record(self, session: RunningSession) -> None:
        sessions = self._load()
        sessions[session.agent_id] = session
        self._save(sessions)

    def mark_stopped(self, agent_id: str) -> None:
        sessions = self._load()
        if agent_id not in sessions:
            raise KeyError(f"no session started for agent {agent_id!r}")
        sessions[agent_id] = replace(sessions[agent_id], alive=False)
        self._save(sessions)

    def get(self, agent_id: str) -> RunningSession:
        return self._load()[agent_id]

    def all(self) -> list[RunningSession]:
        return list(self._load().values())

    def _load(self) -> dict[str, RunningSession]:
        try:
            rows = json.loads(self._registry_file.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        return {agent_id: RunningSession(**row) for agent_id, row in rows.items()}

    def _save(self, sessions: dict[str, RunningSession]) -> None:
        self._registry_file.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._registry_file.with_suffix(".tmp")
        temporary.write_text(json.dumps({k: asdict(v) for k, v in sessions.items()}, indent=2), encoding="utf-8")
        os.replace(temporary, self._registry_file)
