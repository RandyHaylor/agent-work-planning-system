# Spec: citation enforcement and client review mode

DRAFT (agent-approved under the user's build handover; see BUILD-DECISIONS-LOG.md)

## The requirement

User, 2026-11-25 (`05-module-specs.md`, "Enforced citations and client review mode"):

> "what makes it all work is that you can't make a requirement/task/plan etc tha tmakes claims about user requirements/needs or tech realities/solutions or documentation cites, etc, without the formal actual code. source of truth already has a system that verifies that a user quote is included that does validate what was claimed and we need to do that sort of setup. That is the reason we wanted a client to have a rewview mode so it can auto run these reviews. Build that out ... make it work, we'll connect on how it was done later. remember to keep it modular so we can support other harnesses."

> "Talk to unharness dev to find out about mimicing it's pi vm runner in our own env, running our own tiny pi harness and running small minmal mpi sessions using the same gemma4 model that can run on local host."

This **supersedes build log #18** and `05-spec-review-dispatch.md` ("review_dispatch reduces to the planner running an ordinary review task"): reviews of claims now run automatically on a client in review mode.

## Recorded decisions this builds on

- "Every point is demonstrated. Each requirement, decision and technical claim is backed by direct quotes that adequately support it. The sources are the user, the web, documentation, code and other references." (`Top-Down_Planning_Philosophy.md`)
- "No paraphrase as evidence. Quotes are shown as they appear in the source, never restated by the writer. A summary is never treated as proof." (same)
- "Titles make no claims. A title is a short, generic noun phrase naming a topic, such as \"vendor placement\". The quotes underneath carry the claims." (same)
- "A reviewer agent scans every node. Every specification or user decision must cite a user quote that states or acknowledges it. Every technical claim must cite a reference quote that corroborates it." (same)
- "What's checked. Specifications and user decisions need a user quote. Technical claims need a reference quote that corroborates them. A node's claim has to match its quote and add nothing the user didn't approve. A node that relies on a document needs a document quote, or it's rejected." (`Agent_Planning_System_Plan.md`)
- "Async. As in SoT today, review never blocks the agent. It's told the node was submitted for review, not that it was approved, and the result comes back when the review is done." (same)
- "Review queue. The server holds a generic review task queue and sends jobs to reviewer clients that are available and assigned. Any client can be set up in a reviewer role, as part of the server system." (same)
- "Sessions. Reviewer clients run review sessions through their harness adapters, using command-line session control such as `claude -p`." (same)
- "it was clearly stated that the server deploys the reviews from a connected client instance configured to act as a reviewer" (`05-module-specs.md`, Round 2, 8); tree v5: "`review_dispatch/` sends a review node to an available reviewer client, never to two".
- "Nodes are not reviewed; review is a task, not a node state." (`05-module-specs.md`, "Phase 2: project_tree" 1)
- "Keep it simple, nothing special. A reviewer is just an agent you ask questions; it's meant to be a simple call." (`05-module-specs.md`, "Phase 2: access" 1)
- Access spec: "no reviewer role (a reviewer is a worker)" (`05-spec-access.md`).
- "for where we're at, the planner is the one that starts/stops tasks." (`05-module-specs.md`, "Build handover and process")
- "Ensure you build modularly, avoid monoliths, etc" (same)
- Citation string format `[<reference id>:<start>-<end>]`, 1-based inclusive lines (build log #40, `references/citation_format.py`); "a node cites a reference if it's one of its content items or its text contains `[ref:start-end]`" (build log #43).
- "One generic node type. Never create separate types for things that are a property or state of a node (reviews, escalations, proposals are ordinary nodes/content; \"queues\" are views by state)." (`CLAUDE.md`)
- `GET /nodes?project_id=&state=` for nodes by state (build log #17); planner may create supplementary tasks (build log #26).

## Plain statement

Two layers, as in source-of-truth (SoT):

1. **Deterministic gate (server, code).** SoT's `requirements_reference_validator.py` rejects a change whose quote reference doesn't resolve or whose range is out of bounds. Ours: every content write on a node must carry a **claim tag**; a claim tag says which kinds of evidence it needs; the text must contain at least one citation of that kind, and every citation must resolve and be in range. Otherwise the write is rejected with 422 and a message saying exactly what to add. Titles get SoT's deterministic title checks. Nothing is written when the gate fails.
2. **Semantic review (client, model).** SoT's `requirements_modification_reviewer.py` asks a reviewer session whether the cited slice actually supports the operation. Ours: each accepted content write opens a **review record**. A client in **review mode** polls, takes one record (never two clients: `SKIP LOCKED`), gets a packet with the quotes already resolved and inlined (SoT's "no Read needed" pattern), runs a pluggable reviewer backend, and submits `pass` / `fail` + reason. Async, as decided: the writer is told "submitted for review", never "approved".

### Reconciling "nodes are not reviewed; review is a task"

- A review record is a **record about one content item** (one reference id), not a node state and not a node type. Nodes keep their four states; nothing about a node changes when a review passes or fails. "Queues" stay views: pending/failed reviews are queries over review records.
- The reviewing work runs as an **ordinary task**: the planner creates one standing task node per project labelled `review` (title e.g. "citation review"), assigns it, and mints its worker token as for any task. The review-mode client runs under that worker token. This keeps "a reviewer is a worker" (no new role) and "the planner starts/stops tasks" (the planner starts or stops review mode by starting/stopping that task).
- FLAGGED: Round 2 #8 / tree v5 ("server deploys reviews to a reviewer client") and #18 / the review-dispatch spec ("planner runs a review task") pulled in opposite directions. This spec does both in the smallest way: the server holds the records and hands them out (pull, not push); the client doing it is a worker on a planner-started review task. User to confirm.

## Claim tags (the policy)

Every `POST /nodes/{id}/content` and `PUT /nodes/{id}/content/{ref}` must carry exactly one claim tag (other descriptive tags may be added). Derived from SoT's node kinds (`quote_reference` = cited requirement, `group` = no claim) and our docs' categories (requirement, decision, technical claim, documentation, plan/spec).

| Claim tag | What it claims | Needs at least one citation of origin | Every citation must be of origin |
|---|---|---|---|
| `requirement` | a user requirement or need | `user_exchange` or `proposal_response` | any evidence origin |
| `decision` | a user decision | `user_exchange` or `proposal_response` | any evidence origin |
| `technical` | a technical reality or solution | `document` or `knowledge_base` | any evidence origin |
| `documentation` | what a document/doc page says | `document` or `knowledge_base` | `document` or `knowledge_base` |
| `plan` | a plan/spec/task description combining the above | any evidence origin | any evidence origin |
| `note` | no claim (SoT's `group`: structure, a question, a status report) | none | any evidence origin |

- "Evidence origins" = `user_exchange`, `proposal_response`, `document`, `knowledge_base`. **Origin `node` never counts as evidence** ("A summary is never treated as proof"): citing another node's text is allowed only alongside qualifying evidence citations, and doesn't satisfy a requirement row.
- Web pages and code arrive as `document` references (loaded through the reader and cited; `ORIGIN_DOCUMENT` = "anything the reader loaded and an agent cited"). Knowledge bases are deferred (build log #16); the origin stays in the policy.
- `note` is still reviewed semantically: the reviewer fails it if it actually makes a requirement/technical claim (closes the "just tag it note" hole).
- The policy is one table in code (`claim_policy.py`), loaded from configuration so the set can grow without code changes elsewhere.

## Deterministic checks (in order; first failure -> 422)

1. **Claim tag present.** Exactly one of the claim tags. Error: `content needs exactly one claim tag: requirement, decision, technical, documentation, plan, note (got: [...])`.
2. **Citations parse.** `citation_format.citations_in(text)`. Bracketed text that looks like a citation but doesn't match the format (e.g. `[ref-x:12]`) is an error: `malformed citation "[ref-x:12]": expected [reference-id:start-end]`.
3. **Each citation resolves.** `ReferenceLibrary.get(id, follow_superseded=False)`; unknown -> `reference ref-... does not exist`. A temp cache id (`tmp-...`) -> `tmp-... is a temp cache item: cite it first (planning cite tmp-... START END) and use the returned reference id`. Superseded -> `ref-a is superseded by ref-b; cite ref-b`.
4. **Each range is valid.** `1 <= start <= end <= line_count(reference)`; error names the reference's line count. (SoT validates `char_range` bounds and minimum length; we use lines per build log #40, and there is no minimum.)
5. **Origin rule.** Per the table. Error: `a "requirement" claim needs a user quote: cite a user_exchange or proposal_response reference (planning quotes / the user's reply). Found only: document`.
6. **Titles** (on create, update, insert_before, supplementary task; SoT's deterministic part): non-empty after trim; at most 50 characters; contains no citation; is not a sentence (no trailing `.`/`!`/`?`). SoT's other title rules (1-5 word noun phrase, no detail beyond the slice) are semantic and go to the reviewer, as in SoT's prompt.

All errors collected? No: first failure only per check stage, but stage 3-5 report **every** bad citation in one message, so the agent fixes them in one pass.

Errors raise `planning_system.contract.Invalid` (already mapped to 422).

## Module list (nested)

```
server/domain/citation_enforcement/        # NEW deep module; one public class
    interface.py        CitationEnforcement (ABC)
    citation_enforcement.py   real: composes the children below
    claim_policy.py     (private) tag -> required/allowed origins table; from config
    citation_checker.py (private) parse, resolve, range, origin checks over ReferenceLibrary
    title_rules.py      (private) deterministic title checks
    fakes.py
server/domain/content_review/              # NEW; replaces the empty review_dispatch placeholder
    interface.py        ReviewLedger (ABC)
    review_ledger.py    real: opens/takes/submits records; lease expiry
    review_packet_builder.py (private) resolves citations into an inlined packet (SoT pattern)
    ports.py            ReviewStoragePort (Postgres impl in storage; SKIP LOCKED)
    types.py, fakes.py
server/commands/
    add_node_content.py, replace_node_content.py   CHANGED: enforce -> write -> open review
    create_node.py, update_node.py, create_supplementary_task.py (and insert_before)  CHANGED: title check
    list_reviews.py, take_review.py, submit_review_verdict.py, release_review.py   NEW
local_client/review_mode/                  # NEW; one public class ReviewModeLoop
    review_mode_loop.py  poll -> take -> backend -> submit
    review_prompt.py     (private) prompt adapted from SoT
    verdict_parser.py    (private) strict JSON; SoT's balanced-brace scan from the end as fallback
    reviewer_backends/
        interface.py     ReviewerBackend (ABC, strategy)
        backend_factory.py  name -> backend (from client config)
        claude_code_backend.py   uses the existing review_worker (persistent `claude -p` session via the Claude Code harness adapter)
        local_llm_backend.py     OpenAI-compatible POST to local llama.cpp gemma4 (default)
        pi_backend.py            tiny pi harness, `pi --mode rpc` JSONL
        fakes.py         FakeReviewerBackend (scripted verdicts)
```

Why this split: enforcement is pure checking over references with no storage of its own (one deep module, three private strategies of rule); the ledger owns review records and their concurrency (one table, one responsibility); the commands are the one place that composes tree + enforcement + ledger, so `project_tree` stays unaware of reviews and `content_review` never writes nodes. `review_dispatch/` is removed (its name described server push, which this design doesn't do).

## Types / public interfaces

```python
# citation_enforcement
CLAIM_TAGS = ("requirement", "decision", "technical", "documentation", "plan", "note")

@dataclass(frozen=True)
class CheckedClaim:
    claim_tag: str
    citations: tuple[Citation, ...]

class CitationEnforcement(ABC):
    def check_content(self, text: str, tags: Iterable[str]) -> CheckedClaim: ...   # raises Invalid
    def check_title(self, title: str) -> None: ...                                 # raises Invalid

# content_review
PENDING, TAKEN, PASSED, FAILED, SUPERSEDED = "pending", "taken", "passed", "failed", "superseded"

@dataclass(frozen=True)
class ReviewRecord:
    id: str                    # "rev-<uuid4>"
    project_id: int
    node_id: int
    content_reference_id: str  # the node content item under review
    claim_tag: str
    status: str
    reviewer: Optional[str]    # agent id holding / having held it
    taken_at: Optional[datetime]
    reason: str                # reviewer's reason (SoT: <= 15 words)
    suggested_title: Optional[str]   # SoT's amended_short_title; NOT auto-applied
    created_at: datetime
    decided_at: Optional[datetime]

@dataclass(frozen=True)
class ResolvedCitation:
    citation: Citation
    origin: str
    quoted_text: str           # exact lines
    pre_text: str              # user_exchange only: what the agent said before (SoT PRE-INPUT CONTEXT)
    full_text: str             # user_exchange/proposal_response: whole entry; documents: "" (slice only)

@dataclass(frozen=True)
class ReviewPacket:
    review_id: str
    node_title: str
    node_context_summary: str
    claim_tag: str
    claim_text: str
    citations: tuple[ResolvedCitation, ...]

@dataclass(frozen=True)
class Verdict:                 # SoT PerOperationVerdict, one op per review
    passed: bool
    reason: str
    suggested_title: Optional[str] = None

class ReviewLedger(ABC):
    def open(self, project_id: int, node_id: int, content_reference_id: str, claim_tag: str) -> ReviewRecord
    def supersede_for(self, content_reference_id: str) -> None     # on replace_content
    def list(self, project_id: int, status: Optional[str] = None, node_id: Optional[int] = None) -> list[ReviewRecord]
    def take_next(self, project_id: int, reviewer: str) -> Optional[ReviewPacket]   # SKIP LOCKED; None if empty
    def submit(self, review_id: str, reviewer: str, verdict: Verdict) -> ReviewRecord  # only the holder
    def release(self, review_id: str, reviewer: str) -> None        # back to pending
    def expire_leases(self, older_than: timedelta) -> int           # taken too long -> pending

# local_client/review_mode
class ReviewerBackend(ABC):
    name: str
    def review(self, packet: ReviewPacket) -> Verdict: ...   # raises ReviewerUnavailable / UnparseableVerdict

class ReviewModeLoop:
    def __init__(self, api_client, backend: ReviewerBackend, project_id: int, poll_seconds: float = 5.0)
    def run_once(self) -> Optional[str]      # review id handled, or None if nothing pending
    def serve(self, stop: Event) -> None
```

`take_next` SQL: `SELECT ... FROM content_reviews WHERE project_id=:p AND status='pending' ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1`, then set `taken`, `reviewer`, `taken_at` in the same transaction (CommandRunner owns the transaction, build log #13). Lease default 10 minutes, expired at the start of each `take_next`.

## Flow

1. Agent: `POST /nodes/{id}/content {text, tags}`.
2. `AddNodeContent.run`: `enforcement.check_content` (422 on failure) -> `tree.add_content` -> `reviews.open(...)`, one transaction. Response adds `"review": {"id": "rev-...", "status": "pending"}` and the message `submitted for review (not approved)`.
3. `ReplaceNodeContent`: same, plus `reviews.supersede_for(old_reference_id)`.
4. Review-mode client: `POST /reviews/take` -> packet or 204; backend -> `Verdict`; `POST /reviews/{id}/verdict`. Unparseable or backend error: retry once, then `POST /reviews/{id}/release` and log (a broken reviewer must not fail someone's content; SoT denies by default because it blocks synchronously, we don't block).
5. Planner sees failures through the view `GET /reviews?project_id=&status=failed` (CLI `planning review list --status failed`); the planner fixes the content (replace) or, when the user must answer, creates a `requirement request` supplementary task as it already can. The server creates no tasks itself ("the planner is the one that starts/stops tasks").

## Routes (http_api `command_routes`, every route via CommandRunner)

| Route | Command | Who |
|---|---|---|
| `GET /reviews?project_id=&status=&node_id=` | ListReviews | planner of the project, admin, the review-task worker |
| `POST /reviews/take {project_id}` | TakeReview -> 200 packet / 204 | worker whose task node is labelled `review` in that project |
| `POST /reviews/{id}/verdict {passed, reason, suggested_title?}` | SubmitReviewVerdict | the holder only; 409 if not holder or not `taken` |
| `POST /reviews/{id}/release` | ReleaseReview | the holder |

New permission rules in `access` (pure): `CanReviewProject(project_id)` = worker whose own task node is in that project, is labelled `review`, and is `in_progress`. FLAGGED: this widens the worker rule "a worker reads only its own task node" — the packet inlines other nodes' content and quotes for that one labelled task. Planner/admin may also take reviews (manual review).

## CLI (`local_client`, declarative command table)

- `planning review serve --project ID [--backend local_llm|claude_code|pi] [--model MODEL] [--poll-seconds 5] [--once]` — runs `ReviewModeLoop` with the task's worker token (the task runner already puts `PLANNING_TOKEN` in a started session's environment; started by hand it reads the token from the normal client credential store).
- `planning review list --project ID [--status pending|taken|passed|failed|superseded] [--node ID]`
- `planning review show REVIEW_ID`

The planner starts review mode like any task: `planning task start <review task id>` may launch `planning review serve` instead of a harness session when the task is labelled `review` (task_runner change: one branch on the label, choosing the launch command).

## Prompt (adapted from SoT `request_change_set_review`)

One review per prompt, quotes inlined, strict JSON out. Kept from SoT nearly verbatim: "Review fast", "Reply with EXACTLY one JSON object, nothing before/after, no markdown fence", "Reason <=15 words", the TITLE RULE (1-5 word noun phrase, 1-50 chars; wrong shape/scope -> `suggested_title`, not a fail), the two EXPLICITLY-SUPPORTED PATTERNS (brief confirmation answered against PRE-INPUT CONTEXT; user states the requirement directly, overriding the agent's framing), and "Only reject for substantive defects". Added for our tags:

- `technical` / `documentation`: pass only if the cited slice corroborates the claim; fail if the claim adds anything the slice doesn't say ("add nothing the user didn't approve").
- `plan`: every user-facing claim needs a user citation and every technical claim a reference citation; fail naming the unsupported sentence.
- `note`: fail if it makes a requirement or technical claim.
- Paraphrase as evidence (claim restates a quote that isn't cited) -> fail.

Output: `{"passed": true|false, "reason": "...", "suggested_title": null|"..."}`. Parser: `json.loads` on the whole reply; fallback SoT's balanced-brace scan from the end; anything else -> `UnparseableVerdict`.

## Reviewer backends (strategy)

- `claude_code`: wraps the existing `ReviewWorker` (persistent headless `claude -p` session via `AiCliAdapterClaudeCode.spawn_persistent_reviewer_session`, rotation on exhaustion carried from SoT's `reviewer_session_lifecycle_manager.py`). Model from `--model` (default `haiku`); no tools allowed (quotes are inlined); 120 s reviewer timeout (build log #38).
- `local_llm` (**default**, build log #47-#48): direct OpenAI-compatible POST to the existing llama.cpp gemma4 server `http://127.0.0.1:8898/v1/chat/completions`, model `gemma4-31b-jang-q3:latest`, `chat_template_kwargs.enable_thinking=false`, `response_format: {"type": "json_object"}`, temperature 0, small `max_tokens`, request timeout, strictly sequential (one server slot shared with another team). The client never starts or stops that server. httpx with an injected transport (MockTransport in tests).
- `pi`: our tiny pi harness (`tools/pi`, `PI_CODING_AGENT_DIR=tools/pi/agent`, `pi --mode rpc` over JSONL, modelled on `claude-code-cli-runner/claude_code_cli_runner/pi_harness.py`). Live run pending the user's OK; contract tests against a fake pi process.
- Adding a harness = one new class + one factory entry.
- Ports: our services must not use 8765, 8775, 8790, 8898.

## External integration tests (mock up front)

Server, contract tests run against fake and real:

1. `check_content`: no claim tag / two claim tags -> Invalid naming the tag set.
2. `requirement` citing only a `document` reference -> Invalid naming the needed origins; citing a `user_exchange` -> ok.
3. `technical` citing only a `user_exchange` -> Invalid; `document` -> ok. `documentation` citing a `user_exchange` alongside a `document` -> Invalid (every citation must be document/kb).
4. Citation of origin `node` alone never satisfies a rule.
5. Unknown reference, `tmp-` id, superseded reference (message names the replacement), range 0-3, 5-2, end past line count (message gives line count) -> Invalid; all bad citations reported in one message.
6. Malformed citation-like text `[ref-x:12]` -> Invalid.
7. `note` with no citations -> ok.
8. Titles: empty, 51 chars, contains citation, ends with `.` -> Invalid; "vendor placement" -> ok.
9. Ledger: `open` -> pending; two concurrent `take_next` (real Postgres, two connections) never return the same record; `submit` by non-holder -> Conflict; lease expiry returns a taken record to pending; `supersede_for` marks open records superseded.
10. Packet: user_exchange citation inlines quoted lines, full text and pre_text; document citation inlines only the slice.

HTTP (in-process app):

11. `POST /nodes/{id}/content` without valid citations -> 422 with the message; nothing stored; no review record.
12. Valid content -> 201 with `review.status == "pending"`; `GET /reviews?status=pending` lists it.
13. `POST /reviews/take` by a worker not on a `review` task -> 403; by the review-task worker -> packet; queue empty -> 204.
14. Verdict fail -> `GET /reviews?status=failed` shows reason and suggested_title; node state unchanged.
15. Replace content -> old review `superseded`, new one `pending`.
16. Title rule enforced on create node, update node, supplementary task.

Client:

17. `verdict_parser`: clean JSON, JSON after chatter, fenced JSON (accepted via fallback), garbage -> UnparseableVerdict.
18. `ReviewModeLoop.run_once` with FakeReviewerBackend against a mocked api_client: take -> review -> submit; empty -> None; backend error twice -> release.
19. `backend_factory` defaults to `local_llm`; against an httpx MockTransport it sends enable_thinking=false, json_object, temperature 0, and never two requests at once. `pi` against a fake `pi --mode rpc` process exchanges JSONL and parses the verdict.
20. `claude_code` backend against the fake harness adapter: prompt contains the inlined quotes and the JSON contract; reply parsed.
21. **End to end** (in-process server + real ledger on the test database + FakeReviewerBackend): planner creates project and a `review` task, starts it; worker adds `requirement` content citing a stored user exchange; `planning review serve --once` (fake backend scripted to fail) -> planner's `planning review list --status failed` shows it; planner replaces content; second `--once` (scripted pass) -> passed; the old record is superseded.
22. Live (only with `PLANNING_RUN_CLAUDE=1`, build log #27): haiku reviewer passes a requirement citing a clear user quote and fails one citing an unrelated quote.

## Judgement calls (agent)

1. Claim tag required on every content write (untagged -> 422) rather than enforcing only tagged content: otherwise omitting the tag skips the gate.
2. Tag set `requirement, decision, technical, documentation, plan, note`, from SoT kinds + our docs.
3. Origin `node` never counts as evidence.
4. Deterministic title rules limited to SoT's (empty, >50) plus no citation and not a sentence; the rest is the reviewer's.
5. One content item per review (SoT batches a change set; we have no change sets).
6. Suggested title is shown, not auto-applied (SoT auto-persists; here only the planner edits nodes).
7. Pull with SKIP LOCKED and a 10-minute lease, not server push.
8. Review mode runs under a worker token on a planner-started task labelled `review`; no new role.
9. Unparseable verdict -> retry once, then release (not fail).
10. Planner notified by the failed-reviews view, not by server-created tasks.
11. `review_dispatch/` placeholder replaced by `content_review/`.
12. No gating of `done` on reviews in this spec (open: should a node with failed/pending reviews be allowed `done`?).

## Conflicts / open points for the user

- Server-pushed review (Round 2 #8, tree v5) vs planner-run review task (#18): reconciled as pull by a worker on a review task; confirm.
- Worker read scope widened for the review task (packets inline other nodes' content and quotes).
- Existing guidance/presets don't mention claim tags; they must be updated or every current content write 422s.
- Live `pi` run waits on the user's OK; `local_llm` shares one llama.cpp slot with another team (sequential only).
