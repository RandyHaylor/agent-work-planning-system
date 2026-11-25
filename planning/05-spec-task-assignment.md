# Spec: task_assignment (server) + starting/stopping tasks (planner's harness)

DRAFT (agent-approved under the user's build handover; see BUILD-DECISIONS-LOG.md)

## Recorded decisions this builds on

- "for where we're at, the planner is the one that starts/stops tasks. if the task is very large, the planner can spawn a dev manager (also a planner) so it can remain higher level and not run out of context." (`05-module-specs.md`, "Build handover and process")
- "I feel like this system is set up so a planner/admin assigns tasks." Task nodes are assigned by the planner or admin, who mints the worker's scoped token; workers never pull work. (`05-module-specs.md`, Round 5, "No claiming")
- "revert to the planner creating all the tasksk though i was wrong about that we're not using recursion to have tasks split themselves up here." (`05-module-specs.md`, "Phase 2: access" 4)
- "A literal tool the worker can call: create supplementary task ... The worker doesn't choose where it goes; it always goes right before its own task." (`05-module-specs.md`, "Phase 2: access" 2)
- "when a task inserts a tech spike or requirement request as a sibling before itself, always add it to that task's depends-on." / "If it isn't specified, a task depends on the sibling before it by default." / "the planning/admin agent decides who runs, and it can choose to run things in parallel." (`05-module-specs.md`, "Phase 2: project_tree" 3)
- "With a mainstream harness such as the Claude CLI, the primary agent sees a task to assign, spins up an agent, and gives it the access it needs to start on that task." (`Agent_Planning_System_Plan.md`, "Task assignment and isolation")
- Isolation: "left to the user and primary agent. The system recommends worktrees or branches and records which branch a task's work is on." (`05-module-specs.md`, Round 2, 4)
- "Spawned agents don't know about the system; the planner does. ... Workers don't learn the system (their task carries their context)" (`05-module-specs.md`, "Gap 1" 2)
- Planner token: "a token scoped to one project, acting as that project's admin" (`05-module-specs.md`, "Audit answers" 2)
- Claude Code only in v1, harness interface kept for Codex (`05-module-specs.md`, "Gap 2")
- Routes: `POST /nodes/{id}/assign {agent_id, branch} -> {node, worker_token}`, `POST /nodes/{id}/state`, `GET /nodes/{id}/ready-children`, `POST /credentials`, `POST /credentials/{id}/revoke`, `GET /nodes/{id}/context`, `GET /guidance/{role}` (`BUILD-PLAN.md`)
- Build log #7: "task_assignment beyond assign+mint" is out of the first build.

## Split of responsibility

| Who | Does |
|---|---|
| Server `task_assignment` | One command: assign a task node to an agent ID, record the branch, set state `assigned`, mint the worker's scoped token, all in one transaction. Nothing else. The server never starts or stops processes. |
| Planner (an agent, using the CLI) | Picks what runs (`ready-children`), calls assign, starts the worker session, watches it, stops it, sets states, revokes the token when done. |
| `local_client` session runner (harness adapter) | The mechanics of starting/stopping a headless Claude Code session on the planner's machine. No planning logic. |

## Module list

```
server/domain/task_assignment/
  task_assigner            assign + mint in one call; uses ProjectTree.assign, CredentialIssuer.mint, AgentRegistry.touch
server/commands/
  assign_task              command class (permission: PermissionPolicy.can_assign + can_mint)
local_client/task_runner/  (spec: 05-spec-local-client.md)
  task_session_launcher    builds the start prompt, calls the harness adapter's session runner
```

## Types

```python
@dataclass(frozen=True)
class Assignment:
    node: Node                       # state "assigned", assignee, branch set
    worker_token: str                # plaintext, shown once
    credential_id: CredentialId

@dataclass(frozen=True)
class TaskStartRequest:              # local_client side
    node_id: NodeId
    agent_id: AgentId                # also the Claude session id (one id, registry key)
    role: str                        # "worker" | "planner" (dev manager)
    token: str
    working_directory: Path          # worktree/branch chosen by planner or user
    allowed_tools: tuple[str, ...] = ()
```

## Public interface

```python
class TaskAssigner:                  # server domain
    def assign(self, issuer: Principal, node_id, agent_id, branch) -> Assignment
        # rejects: node not a leaf task in issuer's project, node done/abandoned
```

Flow for the planner (all through the CLI):

1. `planning nodes ready <parent>` -> pick task(s); may start several in parallel.
2. `planning task assign <node> --agent <id> --branch <b>` -> worker token.
3. `planning task start <node> --agent <id> --token <t> --dir <worktree>` -> local_client spawns `claude -p` with `PLANNING_TOKEN` in its environment and a start prompt = `GET /guidance/worker` text + `GET /nodes/{id}/context`.
4. The worker works, may call `planning supplementary create` (sibling inserted before its task, added to depends-on), turns in via `planning content add`.
5. `planning task stop <agent>` terminates the session if needed; `planning nodes state <node> done|abandoned`; `planning credentials revoke <id>`.

**Dev manager:** for a very large task the planner starts a session with role `planner` instead of `worker`, same launcher, start prompt = `GET /guidance/planner` + the node's context. The dev manager then runs this same flow for the children of that node. Its token: `access` lets a planner mint workers only, so the dev manager's planner token is minted by admin (`POST /credentials {role: planner, ...}`) or the planner passes its own project token. OPEN (flagged): which one; the scaffold supports both.

## External integration tests (mock up front)

1. assign sets assignee, branch and state `assigned`, and returns a worker token that authenticates as worker scoped to that node (mock credential store).
2. A planner can't assign outside its project; a worker can't assign at all.
3. Assigning a done or abandoned node fails with `Invalid`.
4. Assign + mint is atomic: if minting fails, the node is unchanged.
5. Revoking the planner's credential revokes the worker tokens minted by assign.
6. `task start` (mocked harness adapter) launches one session with the token only in its environment, never in the prompt text, and the prompt contains the worker guidance and assembled context.
7. `task start --role planner` uses planner guidance.
8. `task stop` terminates the handle; the node's state is not changed by stop.
