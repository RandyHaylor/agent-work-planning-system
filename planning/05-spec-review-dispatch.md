# Spec: review_dispatch

DRAFT (agent-approved under the user's build handover; see BUILD-DECISIONS-LOG.md)

## Recorded decisions this builds on

- "for where we're at, the planner is the one that starts/stops tasks." (`05-module-specs.md`, "Build handover and process")
- "Keep it simple, nothing special. A reviewer is just an agent you ask questions; it's meant to be a simple call." (`05-module-specs.md`, "Phase 2: access" 1)
- "Nodes are not reviewed; review is a task, not a node state." (`05-module-specs.md`, "Phase 2: project_tree" 1)
- "Review is not a code area. A review is an ordinary task" (`05-module-specs.md`, under tree v4)
- Older: "it was clearly stated that the server deploys the reviews from a connected client instance configured to act as a reviewer" (`05-module-specs.md`, Round 2, 8); tree v5: `review_dispatch/ sends a review node to an available reviewer client, never to two`.
- Build log #7: review_dispatch is out of the first build.

## Plain statement

**review_dispatch reduces to the planner running a review task.** A review is an ordinary task node labelled `review`, placed by the planner (usually after the work it checks, with depends-on). The planner assigns and starts it exactly like any other task (`05-spec-task-assignment.md`). There is no server-side dispatcher, no queue, no "never to two" logic: one assignee per node already guarantees one reviewer.

**FLAGGED conflict:** Round 2 #8 and tree v5 say the *server* deploys reviews to a connected reviewer client. The later decision "the planner is the one that starts/stops tasks" (2026-11-25) supersedes that for this build. This spec follows the later decision; the user should confirm whether server-pushed review is dropped or only deferred.

## Module list

None new on the server. `server/domain/review_dispatch/` stays an empty placeholder in the scaffold (no code) until the conflict is resolved.

Client side, "a simple call": `local_client/review_worker/` (see `05-spec-local-client.md`) is a tiny helper the planner can use to ask a reviewer a question and get the answer back, using the harness adapter's persistent session (carried from SoT's `reviewer_session_lifecycle_manager.py`).

## Types / public interface

```python
class ReviewWorker:                       # local_client, no server logic
    def ask(self, question: str, context_paths: list[Path] = ()) -> str
        # sends the question to a persistent headless reviewer session; returns its answer text
        # rotates to a fresh session on context exhaustion (carried from SoT)
```

Recording a verdict = the reviewer (or planner) adds content to the review node (`POST /nodes/{id}/content`, tags e.g. `verdict`) and the planner sets it `done`.

## External integration tests (mock up front)

1. A node labelled `review` is assigned, started and turned in through exactly the same routes as any task (mocked server).
2. `ReviewWorker.ask` returns the mocked session's answer; a second `ask` reuses the same session.
3. On a mocked context-exhaustion response, `ask` rotates to a new session and retries once.
