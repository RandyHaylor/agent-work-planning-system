"""running_sessions_registry: local JSON file of every process this client started (task sessions, review loops,
reviewer processes). Several processes write it (a review loop and its reviewer turns, `planning halt`), so each
read-modify-write holds an exclusive lock on a sibling lock file (POSIX flock; no lock where fcntl is missing)."""
from __future__ import annotations

import json
import os
from contextlib import contextmanager
from dataclasses import asdict, replace
from pathlib import Path
from typing import Iterator

from .interface import RunningSessionsRegistryInterface
from .types import RunningSession

try:
    import fcntl
except ImportError:                     # Windows: single-writer use only
    fcntl = None


class RunningSessionsRegistry(RunningSessionsRegistryInterface):
    """{agent_id: RunningSession fields}, rewritten atomically on each change."""

    def __init__(self, registry_file: Path):
        self._registry_file = Path(registry_file)

    def record(self, session: RunningSession) -> None:
        with self._locked():
            sessions = self._load()
            sessions[session.agent_id] = session
            self._save(sessions)

    def mark_stopped(self, agent_id: str) -> None:
        with self._locked():
            sessions = self._load()
            if agent_id not in sessions:
                raise KeyError(f"no session started for agent {agent_id!r}")
            sessions[agent_id] = replace(sessions[agent_id], alive=False)
            self._save(sessions)

    def forget(self, agent_id: str) -> None:
        with self._locked():
            sessions = self._load()
            if sessions.pop(agent_id, None) is not None:
                self._save(sessions)

    def get(self, agent_id: str) -> RunningSession:
        return self._load()[agent_id]

    def all(self) -> list[RunningSession]:
        return list(self._load().values())

    @contextmanager
    def _locked(self) -> Iterator[None]:
        if fcntl is None:
            yield
            return
        self._registry_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self._registry_file.with_suffix(".lock"), "a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def _load(self) -> dict[str, RunningSession]:
        try:
            rows = json.loads(self._registry_file.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        return {agent_id: RunningSession(**row) for agent_id, row in rows.items()}

    def _save(self, sessions: dict[str, RunningSession]) -> None:
        self._registry_file.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._registry_file.with_suffix(f".{os.getpid()}.tmp")
        temporary.write_text(json.dumps({k: asdict(v) for k, v in sessions.items()}, indent=2), encoding="utf-8")
        os.replace(temporary, self._registry_file)
