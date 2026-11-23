# Agent planning system: project memory

This repo is the base for the **agent planning system**: one harness-agnostic system on Postgres that runs top-down planning, where every requirement and technical claim is backed by real quotes from the user, the web, documentation and code. The existing code (`ai_project_planning_server/`) is the current planning server; the new system is being planned in `planning/` and will be built from it, adapting source-of-truth, fastReader and quick-json-reader into it.

**Start here:** `planning/HANDOFF.md` (current state and next steps), then `planning/process-levels.md`.

## Where things are

- `planning/process-levels.md`: the agreed process levels and all process decisions, with the user's words.
- `planning/01-what-were-doing.md` … `planning/05-module-specs.md`: one file per level. Levels 1-4 are approved; level 5 is in progress.
- `planning/Top-Down_Planning_Philosophy.md`, `planning/Agent_Planning_System_Plan.md`: the user's two source docs, updated to match the decisions.
- Old docs at the repo root (`README.md`, `PLAN.md`, `DEV_PLAN.md`, `WORKFLOWS.md`, `agent-planning-system.md`, `skill/SKILL.md`) describe the CURRENT server. Where they conflict with `planning/`, `planning/` wins (e.g. the README's "a workorder never holds a whole project" is old guidance).

## How to work with the user

- **Honor system.** Until the system can hold quotes itself: do the research yourself and include links; record the user's requirements as close to their own words as you can. There is no file-and-line citation system and no recording mechanism to build.
- **Nothing enters a plan doc without the user's explicit approval.** Propose, get a yes, then write. Drafts are clearly marked DRAFT / not approved.
- **Questions: one at a time,** in the order that makes most sense, using the AskUserQuestion tool with multiple-choice options where possible. Each question must stand on its own (the dialog hides earlier text). Put long drafts in plain text or a file, never only inside a question.
- **Don't guess.** If something isn't in `planning/`, ask. Your technical knowledge is input, not a verdict.
- **Git:** work on `main`, no branches (branches only once agents split off onto separate modules). Commit and push at each milestone or approved change.
- **Write plainly.** Short, concrete; no filler. The user is a senior engineer; don't lecture.

## Software design rules (for this project AND for the system's own prompting and docs)

- A **module** is a normal code module: a cohesive unit with a clear responsibility and an interface, often small (one file of helpers, one strategy, a small folder). Modules can be broken down into task-sized work.
- Module separations MUST be chosen for good software architecture and encapsulation, NOT by subject matter or by upstream lists of project needs. Never "X operations/service/manager" groupings of everything about a subject.
- **Nest modules** where it makes sense rather than sprawling siblings with cross-dependencies. A parent exposes one public interface; children stay private.
- Prefer **proven patterns** (strategy, adapter, facade, factory, command...) only where they add value and reduce or encapsulate complexity, never for their own sake.
- Lean on **tried-and-true design**: SOLID, maintainable, sensible, readable. OOP style is preferred.
- **Don't reinvent wheels.** Research common patterns and existing libraries first; use them or build the conventional pattern.
- **No business logic in any UI.** The Gradio web UI and the CLI are HTTPS clients only. The HTTPS interface does everything, including user actions.
- **One generic node type.** Never create separate types for things that are a property or state of a node (reviews, escalations, proposals are ordinary nodes/content; "queues" are views by state).

## Lessons from planning (2026-11-22/23)

The agent repeatedly produced "modules" that were subject groupings (content items, approval queue, escalations, "<subject> operations"), queue items with "kinds" (hidden types), and a review "module" that was really a task. Each would have been a badly encapsulated module. Design the code as a senior engineer would; check every proposed module against the rules above before showing it.
