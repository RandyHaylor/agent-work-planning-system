"""Fakes for system_halt: an in-memory halt store."""
from __future__ import annotations

from .ports import HaltStoragePort


class InMemoryHaltStore(HaltStoragePort):

    def __init__(self):
        self._halts = {}

    def all(self):
        return list(self._halts.values())

    def put(self, halt):
        self._halts[halt.project_id] = halt

    def remove(self, project_id):
        return self._halts.pop(project_id, None) is not None
