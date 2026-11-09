# Agent Planning System: Decisions & Open Items
As of 2026-11-04

## Goal and scope of this doc
Goal: a Postgres-based hosted server that agents use to follow the process below.
- The server hosts:
  - Knowledge base: product, company, broader context. Read-only to working agents. Changes go through a document handed off to the user; the planning agent applies them once approved.
  - Tasks: planned by a planning agent with the user, per the rules below.
  - Instruction docs: one per piece of work, read-only to the assigned dev agent. The dev agent writes its own docs underneath.
- This doc covers only what was stated or decided. Anything unsettled is in "Left to plan, decide, or discuss".
- "User" means whoever is calling: a person, an agent, a team, anything.

## Decided: role and order of work
The user's role: writing requirements and interfaces, not code.
1. Define the work: a cohesive definition of what's being done, plus definition of done.
2. Define the interfaces and types to create or implement.
3. Survey what exists: interfaces, deep modules (see "Starting point").
4. Decide what to change, what to add, and what to improve first.
- Modules, interfaces, abstractions, and names are decided up front in a planning session, never on the fly.

## Decided: standing rules for all agents
Hard rules that apply without being restated each time.
- Abstraction: nothing is named or built for its implementation. Modules don't know their consumers wherever that's possible.
  - Example: a module that applies a strategy function to a string is a "string strategy processor". It is not a "customer iData file renamer", and not even a "renamer".
- Enforcement: rules are written up front for agents to read, AND checked in a review step.
- Isolation: any module that can be built as a standalone tool must be.
  - Generic, with no knowledge of the parent project. It may still live in the repo (e.g. a utilities folder).
  - Own documentation, own unit tests, own real integration tests.
  - The point is the isolation discipline, not reuse.
- Nested modules: same paradigms, within reason.
  - Planned up front when obvious.
  - For known or obvious kinds of things, the caller can explicitly grant permission to make internal design calls within an approved interface and spec. Standing rules still apply.
- Never make up additional details or rules (added 2026-11-09):
  - Agents infer and guess far too much. An agent must never add a detail, a limit, a number, or a rule that the user did not state, when translating requirements or instructions.
  - "Be brief" does not mean "one line".
  - Where something is genuinely undecided and must be filled, the agent says so, marks it as its own assumption, and asks. It does not quietly turn the assumption into a rule.
- Proof before reliance, proof before done (added 2026-11-05):
  - Nothing about a system is known to work the way we think until a real integration test or actual use proves it. No agent moves forward on an assumption about existing behavior; it proves it first.
  - The same level of proof is required before any work is called done. Unit tests passing means it is time to integration test, not that the work is finished.
  - "Real" means the way the end consumer uses it: real entry points, real services, real data. Anything mocked or partial needs explicit approval and does not count as proof.

## Decided: definition of done and testing
Definition of done varies by task, but it always includes:
- Accomplishes the goal.
- Meshes with existing code and the existing product.
- Required refactoring and documentation are done.
- Real unit tests that follow the project's paradigms and rules.
- The dev agent documents what it builds (required).
- Integration tests are fully real, run the way the end consumer would use it: real API keys, real GPU, real licensed/AI/processing services.
  - Anything mocked, partial, or propped up needs explicit approval.
  - Testing through internal entry points instead of the end-user-facing ones doesn't count.

## Decided: starting point (understanding existing code)
Nothing about the existing system counts as understood until a real test proves it. This is a strict starting point for any work.
1. Start from the knowledge base and from the user, by asking or confirming: "does it do this?"
2. Do targeted code checks. Reading code gives only "it seems like it does this."
3. Prove it with real tests: use existing integration tests, edit them, or create them (including small test apps).
4. Iterate autonomously. Return only on hitting a wall, or with an understanding that can be proven.
- No sweeping a large codebase to reverse-engineer it (no 10–20 minute scour).
- A time-intensive deep dive happens only with permission, when tests or understanding are missing. Results are documented and offered as a proposed knowledge base change.
- Tests built here are added to the codebase, aligned to the layers of the application stack.

## Decided: context control and knowledge base
Why this section exists: agents given the big picture build what they imagine. Every lane, token, and read-only doc below is there to keep an agent on its task with the right context, not to secure anything against a determined agent. That is the user's job through isolation, if they want it.
- Dev agents don't get the broader context. They see their own node, what is beneath it, the knowledge base, and the workorder's environment doc.
- The planning agent (lead / orchestrator) is the admin. It holds the broader context, sees every workorder, and answers dev agent escalations. It shares no more context than strictly necessary and keeps concerns separated.
- Dev agents are encouraged to escalate questions.
- Knowledge base: read-only to working agents. Agents propose changes or additions as a document handed off to the user. The planning agent applies a proposal only after the user approves it (added 2026-11-05).
- Plan scope builds on the knowledge base (product definition, rules, term definitions, deliverables). It must mesh with existing reality and changes only what the plan explicitly says is added or changed.

## Decided: escalation and authority
- Approval comes from the caller, not a hard-coded human. The caller knows what authority it has.
- No agent may change scope, interfaces, or the high-level plan without the user.
- A dev agent can't change its assigned doc. For questions, issues, clarifications, or changes, it escalates to its parent agent.
- The parent agent:
  - Answers what it can.
  - May clarify or adjust only within its broader scope and spec, and only with no conflict.
  - Logs every question in the plan, as a running record of what agents need.
  - Notes obvious, non-scope decisions for later review without stopping work.
- Scope change, interface change, or conflict: that dev agent pauses, and it escalates straight to the user.
- An unaccounted-for scope contradiction can't be acted on by any agent.
- Build as much as possible to spec, then stop.
  - A piece that can't be built to spec is left incomplete, never replaced with something else.
  - A roadblock, or a spec found not to work, halts and asks for approval.
- The question log serves two purposes: feeding better context into future plans, and an audit trail.

## Decided: plan format
- Brief and slide-like: bulleted sentence fragments, easy to read. No multi-page AI plan dumps.
- What the user reviews: seams, interfaces, types, what's important, flow, user story.
- Holds: rules, assignments, definitions of done, test expectations, and explicit written definitions of interfaces and types.
- It's planning documentation, not code or typed data.
- Pieces are called nodes.
- The planning agent creates it with the user. It's read-only to coding agents and reviewable by the user.

## Decided: the system
- A process and a set of rules, not an AI system.
  - Not tied to Claude, AI harnesses, or any specific tool.
  - Works with all humans, all agents, or any mix. The rules still stand.
- Requirements:
  - Fully open source (no open-core or source-available licences).
  - Lightweight.
  - Nesting deep enough for real plans. (Settled 2026-11-05: no limit in the data model; four working levels of task breakdown per workorder, then the branch becomes its own workorder.) A workorder is the unit of work (renamed from "project" 2026-11-09): A workorder is a feature, a sprint's worth of work, a larger tech spike, a broad research phase, or a fix. It is never used to fully encapsulate a large project, app, product, or long-term task. Those are defined in the product or company knowledge base by the admin agent, and updated through documents that planning or dev agents submit to an admin agent, who updates the central knowledge bases.
  - Reliably prevents agents from editing what they aren't permitted to.
  - Central and hosted. (Scoped 2026-11-05: a local tool on one developer's machine for now; multiple agents on that machine. Remote agents are not a current requirement.)
- Chosen direction: a Postgres-based hosted server, possibly hand-rolled, possibly with a handwritten server.
- Task flow:
  1. A task is planned by the planning agent with the user, per the rules.
  2. The planning agent, or a dedicated dev manager agent, deploys dev agents for the modules, features, spikes, or whatever the work needs.
  3. Each dev agent gets a Postgres/app auth token for its portion.
  4. Its instruction doc (DoD, interfaces, types, etc.) is read-only to it.
  5. It writes its own documentation in a doc under its instruction doc.
- Agents may spawn sub-agents if permitted. Each gets its own space beneath. This is a repeatable, nestable pattern.

## Considered and ruled out
- GitHub Issues: not quite right.
- Trello: doesn't nest deep enough, and too rigid.
- Notion: too feature-heavy.
- Outline, Docmost: not fully open source.
- Wiki.js with Git sync: hacky, and permissions don't hold.
- BookStack: limited nesting depth.
- SSH/SFTP access to files: too much.
- Plain files over FTPS: considered, then superseded by the Postgres direction.

## Settled since this doc was written (see PLAN.md for detail)
- Node contents: a plain container with one summary doc; everything else is an attached doc with a role. Bodies are markdown, not JSON.
- An assigned agent writes its own docs on its node and creates nodes beneath it. It never edits the planner's docs.
- The planning agent deploys dev agents. A dev manager is the same role.
- A handwritten FastAPI server in front of Postgres issues app tokens with a role and a scope.
- Escalations are docs on the worker's node, answered in place by the planner; `GET /escalations` lists the open ones.
- Questions and noted decisions are `question` docs on the workorder node.
- A knowledge base proposal is a `kb_proposal` doc; the planner applies it after the user approves.
- Sub-agent spawning: a planner mints tokens; workers do not. Delegated design calls are the named dev-discretion band in each instruction.
- Mock or partial test approvals are `approval` docs on the node.
- The standing-rules review is the planner's closure check, recorded as a `review` doc.
- Proven understanding from the survey is a `survey` doc on the workorder node.

## Still open
- How the user reviews nodes in the slide-like form (the viewer).
- A name for the real-world tests, if "integration test" isn't strong enough.
