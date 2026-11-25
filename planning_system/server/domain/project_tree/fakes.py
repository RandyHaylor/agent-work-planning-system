"""Test support: in-memory tree storage, a ticking clock and a fake ProjectTree."""
import dataclasses
import itertools
from datetime import datetime, timedelta, timezone

from planning_system.contract import Invalid, NotFound

from .interface import ProjectTree
from .ports import Clock, TreeStoragePort
from .types import (ABANDONED, ASSIGNED, DONE, EDITABLE_FIELDS, LINEAR_LEVELS, STATES,
                    SUPPLEMENTARY_LABELS, Node, NodeContent)


class TickingClock(Clock):
    """Every call returns a later time, so each change visibly moves last_verified."""

    def __init__(self, start: datetime | None = None):
        self.current = start or datetime(2026, 1, 1, tzinfo=timezone.utc)

    def now(self):
        self.current += timedelta(seconds=1)
        return self.current


class InMemoryTreeStorage(TreeStoragePort):
    def __init__(self):
        self.nodes: dict[int, Node] = {}
        self.contents: dict[int, list[NodeContent]] = {}
        self._ids = itertools.count(1)

    def new_id(self):
        return next(self._ids)

    def get(self, node_id):
        return self.nodes.get(node_id)

    def save(self, node):
        self.nodes[node.id] = node

    def children(self, parent_id):
        return [n for n in self.nodes.values() if n.parent_id == parent_id]

    def subtree(self, root_id):
        out, todo = [], [root_id]
        while todo:
            node = self.nodes.get(todo.pop())
            if node is not None:
                out.append(node)
                todo.extend(c.id for c in self.children(node.id))
        return out

    def add_content(self, node_id, content):
        self.contents.setdefault(node_id, []).append(content)

    def replace_content(self, node_id, old_reference_id, content):
        items = self.contents.get(node_id, [])
        self.contents[node_id] = [content if c.reference_id == old_reference_id else c for c in items]

    def content(self, node_id):
        return list(self.contents.get(node_id, []))


def _is_main(node):
    return not (node.labels & SUPPLEMENTARY_LABELS) and node.state != ABANDONED


class FakeProjectTree(ProjectTree):
    def __init__(self, storage, references, clock):
        self._s, self._refs, self._clock = storage, references, clock

    # reading
    def get(self, node_id):
        node = self._s.get(node_id)
        if node is None:
            raise NotFound(f"node {node_id}")
        return node

    def children(self, node_id):
        return sorted(self._s.children(node_id), key=lambda n: n.position)

    def ancestors(self, node_id):
        chain, node = [], self.get(node_id)
        while node.parent_id is not None:
            node = self.get(node.parent_id)
            chain.append(node)
        return list(reversed(chain))

    def citing_nodes(self, reference_id):
        from .citing_nodes import CitingNodesFinder
        return CitingNodesFinder(self._s, self._refs).find(reference_id)

    def content(self, node_id):
        self.get(node_id)
        return self._s.content(node_id)

    def _effective_deps(self, node, siblings):
        if node.depends_on is not None:
            return node.depends_on
        earlier = [s for s in siblings if s.position < node.position]
        return (earlier[-1].id,) if earlier else ()

    def ready_siblings(self, parent_id):
        siblings = self.children(parent_id)
        ready = []
        for node in siblings:
            if node.state in (DONE, ABANDONED):
                continue
            deps = [self.get(d) for d in self._effective_deps(node, siblings)]
            if all(d.state in (DONE, ABANDONED) for d in deps):
                ready.append(node)
        return ready

    def list_nodes(self, project_id, state=None):
        nodes = sorted(self._s.subtree(project_id), key=lambda n: n.id)
        return [n for n in nodes if state is None or n.state == state]

    # writing
    def _check_placement(self, parent_id, labels, ignore_id=None):
        if parent_id is None:
            return
        child_level = len(self.ancestors(parent_id)) + 2
        if child_level > LINEAR_LEVELS or (frozenset(labels) & SUPPLEMENTARY_LABELS):
            return
        if any(_is_main(c) for c in self.children(parent_id) if c.id != ignore_id):
            raise Invalid(f"level {child_level} takes one main child; branching starts at level 5")

    def _place(self, parent_id, node_id, position):
        """Put node_id at position among parent_id's children and renumber 0..n-1."""
        others = [c for c in self.children(parent_id) if c.id != node_id]
        position = len(others) if position is None else max(0, min(position, len(others)))
        order = others[:position] + [self._s.get(node_id)] + others[position:]
        for i, child in enumerate(order):
            if child.position != i or child.parent_id != parent_id:
                self._s.save(dataclasses.replace(child, position=i, parent_id=parent_id))

    def _renumber(self, parent_id):
        for i, child in enumerate(self.children(parent_id)):
            if child.position != i:
                self._s.save(dataclasses.replace(child, position=i))

    def create(self, parent_id, title, level_label, context_summary, labels=(), depends_on=None,
               position=None):
        if parent_id is not None:
            self.get(parent_id)
        self._check_placement(parent_id, labels)
        node = Node(self._s.new_id(), parent_id, 10**9, title, level_label, ASSIGNED,
                    frozenset(labels), context_summary, self._clock.now(),
                    tuple(depends_on) if depends_on is not None else None, None, None)
        self._s.save(node)
        self._place(parent_id, node.id, position)
        return self.get(node.id)

    def insert_before(self, task_id, title, labels, context_summary):
        task = self.get(task_id)
        siblings = self.children(task.parent_id)
        old_deps = self._effective_deps(task, siblings)
        new = self.create(task.parent_id, title, task.level_label, context_summary,
                          labels=labels, position=task.position)
        task = self.get(task_id)
        self._s.save(dataclasses.replace(task, depends_on=tuple(old_deps) + (new.id,),
                                         last_verified=self._clock.now()))
        return new

    def update(self, node_id, **fields):
        node = self.get(node_id)
        bad = set(fields) - EDITABLE_FIELDS
        if bad:
            raise Invalid(f"not editable through update: {sorted(bad)}")
        if "labels" in fields:
            fields["labels"] = frozenset(fields["labels"])
        if fields.get("depends_on") is not None:
            fields["depends_on"] = tuple(fields["depends_on"])
        node = dataclasses.replace(node, last_verified=self._clock.now(), **fields)
        self._s.save(node)
        return node

    def move(self, node_id, new_parent_id, position):
        node = self.get(node_id)
        if new_parent_id is not None:
            self.get(new_parent_id)
        self._check_placement(new_parent_id, node.labels, ignore_id=node_id)
        old_parent = node.parent_id
        self._s.save(dataclasses.replace(node, last_verified=self._clock.now()))
        self._place(new_parent_id, node_id, position)
        if old_parent != new_parent_id:
            self._renumber(old_parent)
        return self.get(node_id)

    def set_state(self, node_id, state):
        if state not in STATES:
            raise Invalid(f"unknown state {state!r}")
        node = dataclasses.replace(self.get(node_id), state=state, last_verified=self._clock.now())
        self._s.save(node)
        return node

    def assign(self, node_id, assignee):
        node = dataclasses.replace(self.get(node_id), assignee=assignee, state=ASSIGNED,
                                   last_verified=self._clock.now())
        self._s.save(node)
        return node

    def _touch(self, node_id):
        self._s.save(dataclasses.replace(self.get(node_id), last_verified=self._clock.now()))

    def add_content(self, node_id, text, tags):
        self.get(node_id)
        ref = self._refs.store_node_text(text, node_id)
        content = NodeContent(ref.id, frozenset(tags))
        self._s.add_content(node_id, content)
        self._touch(node_id)
        return content

    def replace_content(self, node_id, old_reference_id, new_text):
        old = next((c for c in self.content(node_id) if c.reference_id == old_reference_id), None)
        if old is None:
            raise NotFound(f"content {old_reference_id} on node {node_id}")
        ref = self._refs.store_node_text(new_text, node_id, replaces=old_reference_id)
        content = NodeContent(ref.id, old.tags)
        self._s.replace_content(node_id, old_reference_id, content)
        self._touch(node_id)
        return content
