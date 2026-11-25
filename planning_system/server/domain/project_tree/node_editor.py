"""node_editor: create, update, move, state, assign (never delete); last_verified on every change."""
from dataclasses import replace

from planning_system.contract import Invalid

from .level_placement_rules import LevelPlacementRules
from .node import NodeReadiness
from .tree_reader import TreeReader
from .types import ASSIGNED, EDITABLE_FIELDS, STATES, Node

UNPLACED = 10**9   # a new node's position until it is slotted in among its siblings


def _normalised(fields):
    """Field values in the shapes Node holds (frozenset labels, tuple depends_on)."""
    out = dict(fields)
    if "labels" in out:
        out["labels"] = frozenset(out["labels"])
    if out.get("depends_on") is not None:
        out["depends_on"] = tuple(out["depends_on"])
    return out


class NodeEditor:
    def __init__(self, storage, clock, placement: LevelPlacementRules | None = None,
                 readiness: NodeReadiness | None = None):
        self._storage = storage
        self._clock = clock
        self._placement = placement or LevelPlacementRules()
        self._readiness = readiness or NodeReadiness()
        self._reader = TreeReader(storage, self._readiness)

    def create(self, parent_id, title, level_label, context_summary, labels, depends_on, position):
        self._check_placement(parent_id, labels)
        node = Node(self._storage.new_id(), parent_id, UNPLACED, title, level_label, ASSIGNED,
                    frozenset(labels), context_summary, self._clock.now(),
                    tuple(depends_on) if depends_on is not None else None, None, None)
        self._storage.save(node)
        self._slot_in(parent_id, node.id, position)
        return self._reader.get(node.id)

    def insert_before(self, task_id, title, labels, context_summary):
        task = self._reader.get(task_id)
        previous_deps = self._readiness.effective_depends_on(task, self._reader.children(task.parent_id))
        inserted = self.create(task.parent_id, title, task.level_label, context_summary, labels,
                               None, task.position)
        self._save_changed(task_id, depends_on=previous_deps + (inserted.id,))
        return self._reader.get(inserted.id)

    def update(self, node_id, fields):
        not_editable = set(fields) - EDITABLE_FIELDS
        if not_editable:
            raise Invalid(f"not editable through update: {sorted(not_editable)}")
        return self._save_changed(node_id, **_normalised(fields))

    def move(self, node_id, new_parent_id, position):
        node = self._reader.get(node_id)
        self._check_not_own_descendant(node_id, new_parent_id)
        self._check_placement(new_parent_id, node.labels, ignore_id=node_id)
        self._save_changed(node_id)
        self._slot_in(new_parent_id, node_id, position)
        if node.parent_id != new_parent_id:
            self._renumber(node.parent_id)
        return self._reader.get(node_id)

    def set_state(self, node_id, state):
        if state not in STATES:
            raise Invalid(f"unknown state {state!r}")
        return self._save_changed(node_id, state=state)

    def assign(self, node_id, assignee):
        return self._save_changed(node_id, assignee=assignee, state=ASSIGNED)

    def touch(self, node_id):
        """Update last_verified only."""
        return self._save_changed(node_id)

    # helpers
    def _save_changed(self, node_id, **changes):
        node = replace(self._reader.get(node_id), last_verified=self._clock.now(), **changes)
        self._storage.save(node)
        return node

    def _check_placement(self, parent_id, labels, ignore_id=None):
        if parent_id is None:
            return
        siblings = [c for c in self._reader.children(parent_id) if c.id != ignore_id]
        self._placement.check(self._reader.depth(parent_id), siblings, labels)

    def _check_not_own_descendant(self, node_id, new_parent_id):
        if new_parent_id is None:
            return
        lineage = {n.id for n in self._reader.ancestors(new_parent_id)} | {new_parent_id}
        if node_id in lineage:
            raise Invalid("a node cannot move under itself")

    def _slot_in(self, parent_id, node_id, position):
        """Put node_id at position among parent_id's children and renumber 0..n-1."""
        others = [c for c in self._reader.children(parent_id) if c.id != node_id]
        position = len(others) if position is None else max(0, min(position, len(others)))
        ordered = others[:position] + [self._reader.get(node_id)] + others[position:]
        self._write_positions(parent_id, ordered)

    def _renumber(self, parent_id):
        self._write_positions(parent_id, self._reader.children(parent_id))

    def _write_positions(self, parent_id, ordered):
        for index, child in enumerate(ordered):
            if child.position != index or child.parent_id != parent_id:
                self._storage.save(replace(child, position=index, parent_id=parent_id))
