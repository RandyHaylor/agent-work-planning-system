"""HaltSwitchService: HaltSwitch over the halt store."""
from __future__ import annotations

from planning_system.errors import Halted

from .interface import HaltSwitch
from .ports import Clock, HaltStoragePort
from .types import Halt, HaltState


class HaltSwitchService(HaltSwitch):

    def __init__(self, storage: HaltStoragePort, clock: Clock):
        self._storage = storage
        self._clock = clock

    def state(self):
        halts = self._storage.all()
        system = next((h for h in halts if h.project_id is None), None)
        projects = tuple(sorted((h for h in halts if h.project_id is not None), key=lambda h: h.project_id))
        return HaltState(system, projects)

    def halt(self, project_id, halted_by, reason=""):
        self._storage.put(Halt(project_id, halted_by, reason, self._clock.now()))
        return self.state()

    def unhalt(self, project_id):
        self._storage.remove(project_id)
        return self.state()

    def ensure_writable(self, project_ids):
        halt = self.state().blocks(project_ids)
        if halt is None:
            return
        scope = "the system" if halt.project_id is None else f"project {halt.project_id}"
        raise Halted(f"halted: {scope} was halted by {halt.halted_by} at {halt.halted_at.isoformat()}"
                     + (f" ({halt.reason})" if halt.reason else "")
                     + "; writes and review hand-outs are refused until an admin un-halts it")
