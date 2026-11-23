# Handoff: agent planning system planning

Written 2026-11-23, at the end of the first planning session (2026-11-22/23). Read `CLAUDE.md` at the repo root first for working rules.

## What this is

We are planning the agent planning system by running its own process on itself, under the honor system. The base is this repo (the current Postgres/FastAPI planning server). Source-of-truth (SoT), fastReader and quick-json-reader are adapted INTO it (their own repos stay untouched): we build versions of what they do on this system's storage, authentication and permissions.

Goal (level 1): "enable planning and scaffolding to allow long running unsupervised trustworthy agent work."

## The process (see `process-levels.md`)

Seven levels, every time (no reduced sets for small requests; simple standalone requests don't use the process):

```
1 What we're doing
└─ 2 Definition of done
   └─ 3 High-level plan  (one node)
      └─ 4 Walkthroughs  (one node; whole-system user stories)
         └─ 5 Module specs   ← first branching
            └─ 6 Test scaffold
               └─ 7 Build
```

- Requirements live on the node they govern and pass down to every node below; never in separate branches.
- Spikes are tasks at any layer; their findings don't pass down by default.
- Knowledge bases are not a level; they are separate stores exposed to a project or not.
- Escalations are events belonging to the node that raised them; the user reviews, fixes from the highest layer needing it down, marks resolved with notes, and the task resumes with an instruction to review the escalation. Workers can never edit their task node.
- Level 5 works in rounds: questions (one at a time, AskUserQuestion, multiple choice) → answers → research and initial design → next questions → repeat.

## Status by level

| Level | Status | File |
|---|---|---|
| 1 What we're doing | Approved | `01-what-were-doing.md` (its "Generally how" is marked as the GitHub README synopsis) |
| 2 Definition of done | Approved, 20 items + hard constraints | `02-definition-of-done.md` |
| 3 High-level plan | Approved; updated with decisions carried up | `03-high-level-plan.md` |
| 4 Walkthroughs | Approved: 3 independent user stories, also the final acceptance tests (one chosen at random is run end to end) | `04-walkthroughs.md` |
| 5 Module specs | In progress | `05-module-specs.md` |
| 6, 7 | Not started | |

## Level 5: decided so far (details in `05-module-specs.md`)

Round 1:
- Fresh schema; existing data not migrated.
- Node content: adjacency list; node row holds title, level label, context summary + last-verified date; everything else is neutral content attached to the node (descriptive tags, version history, write rules); quote pointers link content to a quote range.
- Core: ports and adapters. New core, no HTTP/DB code; Postgres behind storage interfaces; reuse the clean existing parts (permissions approach, admin sessions, backups, test runner).
- No separate MCP server: HTTPS is already agent-first; an agent acting as the user uses admin.
- Gradio is an HTTPS client only. Local client in Python. Postgres tables for claiming. The server deploys reviews to connected client instances configured as reviewers.

Round 2:
- Agent-as-user = admin (same password login window).
- Admin mints a quote-submission credential per local client install ("special key", built on this repo's auth).
- Document fetching: plain HTTP + HTML/PDF converters; JS-only pages fail clearly.
- Isolation (worktrees/branches) left to the user and primary agent; the system records the branch.
- Acceptance tests run by the planner or by workers it assigns, depending on project size. The planner merges on acceptance.

Round 3:
- CLI is an HTTPS client, generated from the server's OpenAPI spec.
- Module tree **v4** (DRAFT, not approved): nested, function-based, OOP; command pattern (`CommandRunner`, `RequestAuthorizer`, `UnitOfWork`, one class per command); facades on `project_tree`, `user_quotes`, `document_sources`, `document_reader`, `api_client`; strategies/factories for fetchers, converters, scanners, harness adapters. Review is an ordinary task (instructions are config), not a code area.
- Existing-solutions research (recommendations, not approved): trafilatura (HTML), pypdf (PDF; check license file), spike specli vs openapi-cli-gen (CLI), Postgres `UPDATE … SKIP LOCKED … RETURNING` (claiming), yoyo-migrations (migrations), keep carried PBKDF2 and SHA-256 token digests.

## Next steps, in order

0. (Session 2, 2026-11-23) Round 4 in `05-module-specs.md`: the document packages (`document_extraction`, `document_reader`, `server/domain/document_sources`) are approved and replace those parts of v4. Next: their public interfaces. Background research comparing extraction strategies and quality checks writes to the session scratchpad; bring its findings to the user.
1. Get the user's approval of the rest of module tree v4 and the research recommendations (ask one at a time). The user is "not 100% convinced on all the modules".
2. Next level 5 round: questions that arise for specs (one at a time).
3. Full specs: public interfaces and types per module, starting with `server/domain`.
4. Spike: specli vs openapi-cli-gen against the server's OpenAPI spec.
5. Then level 6 (test scaffold: hollow modules, integration tests passing against mocks) and level 7 (build).

## Open items and known gaps

- quick-json-reader: a Python port or running its JavaScript (`src/quick_json_reader.js` in its repo) — decide in its spec.
- HTML conversion for citations may need the whole page text, not only the main article — decide in the converter spec.
- Spike backlog from the Plan: Claude desktop hooks; Codex desktop hooks; web chat over HTTPS.
- Agents that can't capture user prompts (web chats, unsupported CLIs/apps) need user approval, forgo guaranteed user quotes, and can still use the web approval queue.
- The Plan's "Points to raise with the user" list (depth trigger, fixed doc roles, summaries vs context summaries, review gating, mocks, admin vs wiki) — several are now settled by level 5 decisions; check the rest when specs reach them.

## How the user wants to work (summary; full list in `CLAUDE.md`)

- Honor system: research yourself and include links; record requirements in the user's words.
- Nothing enters the plan without explicit approval.
- One question at a time, AskUserQuestion, multiple choice, self-contained.
- Work on `main`; commit and push at milestones.
- Software design: modules by architecture and encapsulation, nested, proven patterns only where they add value, SOLID/readable, no reinventing wheels, no logic in UI, one generic node type.

## Session notes

- This session ran as a background job from the Unharness folder; its transcript is `~/.claude/projects/-home-aikenyon-ai-skills-agents-resources-Unharness/b7987975-0ced-4bfe-9cfb-27153434d9e7.jsonl`. Resuming it by ID didn't show the conversation; start new sessions from this repo instead.
- Commit history on `main` records every decision step (`git log -- planning/`).
