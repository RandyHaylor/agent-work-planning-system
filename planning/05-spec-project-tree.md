# Spec: project_tree

APPROVED by the user, 2026-11-23, in Slack: "approve project_tree". Decisions and the user's words are in `05-module-specs.md` ("Phase 2: project_tree"). `assignee` is an agent ID in `agent_registry`.

Built only from recorded decisions: one generic node type, adjacency list, states assigned / in progress / done / abandoned, no deletion, no requirement inheritance (a generic context block passes down), requirement requests and tech spikes are ordinary tasks inserted before the raising task and added to its depends-on, depends-on defaults to the previous sibling, the orchestrator decides what runs, content is stored as fixed references (superseded-by on edit), workers never edit their task node.

## Types

```python
@dataclass(frozen=True)
class Node:
    id: NodeId
    parent_id: NodeId | None
    position: int                    # order among siblings
    title: str                       # generic topic, no claims
    level_label: str                 # "what we're doing", ..., "build"
    state: str                       # "assigned" | "in_progress" | "done" | "abandoned"
    labels: frozenset[str]           # descriptive, e.g. "tech spike", "requirement request", "review"
    context_block: str               # passes down to every node below
    context_summary: str
    last_verified: datetime
    depends_on: tuple[NodeId, ...] | None   # None = the previous sibling
    assignee: PrincipalId | None

@dataclass(frozen=True)
class NodeContent:                   # content attached to a node
    reference_id: ReferenceId        # text is a fixed reference (origin "node")
    tags: frozenset[str]             # descriptive
```

## ProjectTree (the one public interface)

```python
class ProjectTree:
    # reading
    def get(self, node_id) -> Node
    def children(self, node_id) -> list[Node]                 # in position order
    def ancestors(self, node_id) -> list[Node]                 # root first
    def content(self, node_id) -> list[NodeContent]
    def ready_siblings(self, parent_id) -> list[Node]
        # not done/abandoned, and everything in depends_on is done (abandoned ones skipped);
        # lets the orchestrator see what could run in parallel

    # writing (each updates the summary or at least last_verified)
    def create(self, parent_id, title, level_label, context_block, context_summary,
               labels=(), depends_on=None, position=None) -> Node
    def insert_before(self, task_id, title, labels, context_block, context_summary) -> Node
        # requirement request or tech spike: new sibling before the task, always added to its depends_on
    def update(self, node_id, **fields) -> Node
    def move(self, node_id, new_parent_id, position) -> Node
    def set_state(self, node_id, state) -> Node                # who may do it: access/permission_policy
    def assign(self, node_id, assignee) -> Node                # sets state to "assigned"
    def add_content(self, node_id, text, tags) -> NodeContent  # stores text via ReferenceLibrary
    def replace_content(self, node_id, old_reference_id, new_text) -> NodeContent
        # new reference that supersedes the old one
```

Level placement rule: levels 1-4 form a straight line (one child each); branching starts at level 5. Spikes and requirement requests can sit at any level.

## External integration tests (mocked storage and ReferenceLibrary)

1. Levels 1-4 reject a second child; level 5 and below accept many.
2. children come back in position order; move renumbers positions.
3. A node with no depends_on depends on the previous sibling; ready_siblings reflects that.
4. Siblings 1-4 where 3 and 4 depend only on 1: after 1 is done, 2, 3 and 4 are all ready.
5. insert_before puts the new task directly before the raising task and adds it to that task's depends_on, also when the task had an explicit depends_on.
6. Abandoned siblings are skipped in dependency checks and never become ready.
7. No delete exists; abandoning keeps the node and its content readable.
8. Every create/update/move changes last_verified (and the summary when given).
9. A worker's credential can't update its own task node (permission rule enforced).
10. replace_content creates a new reference that supersedes the old; the old stays readable.
11. ancestors returns root first; the context blocks of all ancestors are reachable for context_assembly.
