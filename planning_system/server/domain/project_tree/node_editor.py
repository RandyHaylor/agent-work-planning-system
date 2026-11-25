"""node_editor: create, update, move, state, assign (never delete); last_verified on every change."""
from .level_placement_rules import LevelPlacementRules
from .node import NodeReadiness


class NodeEditor:
    def __init__(self, storage, clock, placement: LevelPlacementRules | None = None,
                 readiness: NodeReadiness | None = None):
        self._storage = storage
        self._clock = clock
        self._placement = placement or LevelPlacementRules()
        self._readiness = readiness or NodeReadiness()

    def create(self, parent_id, title, level_label, context_summary, labels, depends_on, position):
        raise NotImplementedError

    def insert_before(self, task_id, title, labels, context_summary):
        raise NotImplementedError

    def update(self, node_id, fields):
        raise NotImplementedError

    def move(self, node_id, new_parent_id, position):
        raise NotImplementedError

    def set_state(self, node_id, state):
        raise NotImplementedError

    def assign(self, node_id, assignee):
        raise NotImplementedError

    def touch(self, node_id):
        """Update last_verified only."""
        raise NotImplementedError
