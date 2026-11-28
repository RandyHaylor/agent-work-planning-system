"""SessionHalter: `planning halt` / `planning resume` (build log #68). Halt = set the halt marker first (so nothing
new starts, and a review loop that gets the signal aborts at once), then kill every live process in the registry,
each by its whole process group, all at once (SIGTERM, then SIGKILL after the grace), never waiting for a review or
turn to finish."""
from __future__ import annotations

from dataclasses import asdict

from ..task_runner import SESSION_REVIEW_LOOP, SESSION_REVIEWER, SESSION_TASK, RunningSessionsRegistryInterface
from .halt_marker import HaltMarker
from .process_killer import KillTarget, ProcessKiller

# loops first in the report: they are what would start more reviewer turns
_ORDER = {SESSION_REVIEW_LOOP: 0, SESSION_REVIEWER: 1, SESSION_TASK: 2}


class SessionHalter:

    def __init__(self, registry: RunningSessionsRegistryInterface, marker: HaltMarker,
                 killer: ProcessKiller | None = None):
        self._registry = registry
        self._marker = marker
        self._killer = killer or ProcessKiller()

    def halt(self) -> dict:
        """{"halted": True, "killed": [{agent_id, kind, pid, outcome}, ...]}"""
        self._marker.set()
        sessions = sorted((s for s in self._registry.all() if s.alive), key=lambda s: _ORDER.get(s.kind, 9))
        outcomes = self._killer.kill_all([KillTarget(s.pid, s.process_group) for s in sessions])
        report = []
        for session, outcome in zip(sessions, outcomes):
            if session.kind == SESSION_TASK:
                self._registry.mark_stopped(session.agent_id)
            else:
                self._registry.forget(session.agent_id)
            report.append({"agent_id": session.agent_id, "kind": session.kind, "pid": session.pid,
                           "outcome": outcome})
        return {"halted": True, "killed": report}

    def resume(self) -> dict:
        return {"resumed": True, "was_halted": self._marker.clear()}

    def status(self) -> dict:
        return {"halted": self._marker.is_set(),
                "sessions": [asdict(s) for s in self._registry.all() if s.alive]}
