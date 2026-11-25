# Spec: local_client

DRAFT (agent-approved under the user's build handover; see BUILD-DECISIONS-LOG.md)

## Recorded decisions this builds on

- Tree v5 `local_client/` (Python, beside the agent harness): `quote_capture/`, `review_worker/`, `harness_adapters/` (`ai_cli_adapter_interface`, `claude_code/` "adapter, UserPromptSubmit hook, transcript reader, AskUserQuestion capture, installer (SoT); headless sessions via claude -p"), `client_credentials` "the install's quote key". (`05-module-specs.md`)
- "`local_client` nested ... harness_adapters/ (per harness: a capture-hook strategy and a session-runner strategy), client_credentials; all use the same API client." (`05-module-specs.md`, Round 5)
- "lets take codex off the table but PLEASE build it with an interface so we can connect codex later." (`05-module-specs.md`, "Gap 2")
- "prompts are captured to a local client cache, only references are synced to server that was in spec" (same)
- "the planner is the one that starts/stops tasks. if the task is very large, the planner can spawn a dev manager (also a planner)" (`05-module-specs.md`, "Build handover")
- "A reviewer is just an agent you ask questions; it's meant to be a simple call." (`05-module-specs.md`, "Phase 2: access" 1)
- "the admin mints a dedicated credential per local client install. It can only submit user quotes and is revocable" (`05-module-specs.md`, Round 2, 2)
- "Reviewer clients run review sessions through their harness adapters, using command-line session control such as `claude -p`." (`Agent_Planning_System_Plan.md`, "Review queue")

## Module list

```
local_client/                          public: LocalClient (facade used by cli)
  harness_adapters/                    public: AiCliAdapterInterface, adapter_for(config)
    ai_cli_adapter_interface           SoT interface, kept; adds spawn_headless_session (see below)
    claude_code/                       SoT, kept mostly intact
      ai_cli_adapter_claude_code       incl. the claude -p session handle (stream-json, --session-id / --resume, stdin prompt)
      user_prompt_submit_hook, claude_cli_get_recent_agent_messages,
      post_tool_use_capture_askuserquestion_answers, install
    (codex/ later)
  quote_capture/                       spec: 05-spec-quote-capture.md (not repeated here)
  task_runner/                         start/stop task sessions for the planner
    task_session_launcher              TaskStartRequest -> start prompt (guidance + context via api_client) -> adapter session
    running_sessions_registry          local JSON file of sessions this client started (agent id, node, pid, alive)
  review_worker/                       "a simple call": ask a persistent reviewer session a question
    review_worker                      adapted from SoT reviewer_session_lifecycle_manager (rotation on exhaustion)
  client_credentials                   reads/writes the quote key (file, mode 0600, under the client's config dir)
```

`harness_adapters` is the only place that knows Claude Code. `task_runner` and `review_worker` depend on the interface only.

## Types

```python
class PersistentReviewerSessionHandle(ABC):       # SoT, kept; also the handle for task sessions
    session_id: str
    def send_prompt_and_await_response(self, prompt_text) -> str
    def is_alive(self) -> bool
    def terminate(self) -> None

@dataclass(frozen=True)
class HeadlessSessionSpec:
    session_id: str                     # = agent_id registered on the server
    working_directory: Path
    environment: Mapping[str, str]      # PLANNING_URL, PLANNING_TOKEN, PLANNING_CA_CERT
    allowed_tools: tuple[str, ...] = ()
    allowed_read_paths: tuple[Path, ...] = ()
    model: str | None = None
```

## Public interface

```python
class AiCliAdapterInterface(ABC):       # SoT methods kept as they are, plus one:
    def spawn_headless_session(self, spec: HeadlessSessionSpec) -> PersistentReviewerSessionHandle

class LocalClient:                       # facade for the cli
    def install_hooks(self) -> None
    def list_exchanges(self, last: int) -> list[dict]
    def cite_exchange(self, local_exchange_id) -> ReferenceId          # quote_capture.ReferenceSync
    def start_task(self, request: TaskStartRequest) -> str              # returns session id; async, does not block
    def stop_task(self, agent_id) -> None
    def running_tasks(self) -> list[dict]
    def ask_reviewer(self, question, context_paths=()) -> str
```

`start_task` sends the start prompt once and returns; the session runs in a background process; its result is the worker's turn-in on the server, not the process output. The planner watches the tree (`nodes get`, `nodes ready`), not stdout.

## External integration tests (mocked server, fake adapter)

1. start_task registers the agent (`POST /agents`), launches one session with the token only in its environment, records it in the local registry, and returns without waiting.
2. stop_task terminates the session and marks it not alive; the server is not called.
3. A planner-role start uses planner guidance; a worker-role start uses worker guidance.
4. ask_reviewer reuses one session; rotates on exhaustion.
5. The quote key is read only by quote_capture's ReferenceSync; task sessions never receive it.
6. A fake second adapter can replace Claude Code with no change to task_runner, review_worker or quote_capture.
7. Real Claude Code adapter (marked slow, optional): `claude -p` with `--session-id` then `--resume` returns text.
