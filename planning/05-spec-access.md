# Spec: access

APPROVED by the user, 2026-11-23, in Slack: "approve access". Decisions and the user's words are in `05-module-specs.md` ("Phase 2: access").

From recorded decisions only: rules carried from today's `permissions.py` (pure, no I/O); roles admin (browser session, human types the password), planner (token scoped to a whole project; acts as its admin; creates all tasks; kept as today, user decision after the audit), worker (token scoped to its own task); the local client's quote key can only submit user quotes; no reviewer role (a reviewer is a worker); workers never edit their task node; the worker's one write tool is create supplementary task (always placed right before its own task); whoever a requirement request is assigned to answers it; temp cache entries visible to their fetcher + admin; cited references visible to anyone who can see the node.

```python
@dataclass(frozen=True)
class Principal:
    agent_id: AgentId | None         # key into agent_registry (None for the quote key)
    role: str                        # "admin" | "planner" | "worker" | "quote_client"
    project_id: NodeId | None        # planner and worker
    scope_node_id: NodeId | None     # worker: its own task

class PermissionPolicy:              # pure rules; callers pass in the tree facts they need
    # reading
    def can_read_node(self, p, node, ancestors) -> bool
        # admin: all; planner: its project; worker: its task + ancestors' context summaries only
    def can_read_reference(self, p, ref, nodes_citing_it) -> bool
    def can_read_temp_entry(self, p, entry) -> bool            # owner or admin
    def can_read_knowledge_base(self, p, kb) -> bool           # admin; planner; worker only for KBs assigned to it (carried)
    # tree writes
    def can_create_node(self, p, parent) -> bool                # planner in its project, admin
    def can_edit_node(self, p, node) -> bool                    # planner/admin; never a worker on its own task
    def can_set_state(self, p, node, new_state) -> bool
    def can_assign(self, p, node) -> bool                       # planner in its project, admin
    def can_create_supplementary_task(self, p, task) -> bool    # worker on its own task only
    def can_answer_requirement_request(self, p, request) -> bool # its assignee
    def can_add_content(self, p, node) -> bool                  # worker: its turn-in response on its own task
    # references
    def can_submit_user_quote(self, p) -> bool                  # quote_client only
    def can_store_proposal_response(self, p) -> bool            # admin (the user on the website)
    # credentials (carried rules)
    def can_mint(self, p, scope, role) -> bool                  # admin; planner for workers in its project
    def can_revoke(self, p, token_scope) -> bool                # cascades to tokens minted beneath
    def can_rotate(self, p, token) -> bool
```

## External integration tests (pure, no mocks needed)

1. A worker can read its own task and its ancestors' context summaries, and nothing else in the tree.
2. A worker can't edit its own task node, or any node.
3. A worker can create a supplementary task only for its own task.
4. Only the assignee of a requirement request can answer it.
5. A temp cache entry is readable by its fetcher and admin only.
6. A cited reference is readable by anyone who can read a node citing it.
7. Only the quote key can submit user quotes; it can do nothing else.
8. A planner can create, edit, assign and set state only inside its own project.
9. Admin can do everything.
10. Revoking a planner's token revokes the worker tokens it minted.
