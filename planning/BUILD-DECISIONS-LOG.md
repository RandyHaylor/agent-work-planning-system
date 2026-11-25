# Build decisions log

The user handed the build over on 2026-11-25: "You run the show now - we need to get it working as we specified asap. You can now make any calls needed - stay in scope as close as possible. any calls you make, add to a running log file mentinoed in the readme and stored in the repo. Goal: get this usable now for immediate use/testing of what we have so far. The details of hosting/supporting other harnesses, etc are not important. Just our scenario matters now - this local host, claude cli harness adapter."

Every call the agent makes without asking is logged here: date, the call, why.

| # | Date | Call | Why |
|---|---|---|---|
| 1 | 2026-11-25 | New code goes in one new package `planning_system/` beside the old `ai_project_planning_server/` (left untouched, still runnable) | Fresh schema was decided; keeping the old server avoids breaking current use |
| 2 | 2026-11-25 | Same Postgres container, new database `planning_system` | Fresh schema without touching the old server's data |
| 3 | 2026-11-25 | Modules are subpackages of one Python package, not separate installable packages | Decided: "modules ... not always packages"; fastest to wire |
| 4 | 2026-11-25 | Each module that serves HTTP exposes a FastAPI `APIRouter`; `http_api` mounts them | Keeps http_api protocol-only and lets modules be built in parallel |
| 5 | 2026-11-25 | Each module declares its tables on one shared SQLAlchemy `MetaData`; one Alembic history generated after integration | Alembic was decided; one history avoids parallel migration conflicts |
| 6 | 2026-11-25 | Build in 4 parallel worktrees (core server; references + reader; client side; prompt builder), merged to main by the lead | Separate modules with a fixed contract; fewer workers would be slower, more would collide |
| 11 | 2026-11-25 | Level 6 scaffold uses contract tests: each module has an abstract interface (ABC), a fake implementation, and its external integration tests written once and run against every implementation (fake now, real later; the real one is a hollow class raising NotImplementedError, its test run marked xfail until built). Consumers are tested against the fakes of the modules they use | The standard way to have "integration tests passing against mocks" that then prove the real modules |
| 12 | 2026-11-25 | Scaffold of the already-approved domain modules (access, authentication, agent_registry, project_tree, context_assembly, references, quote_capture) starts while the remaining specs are written | They don't depend on the unwritten infrastructure specs |
| 10 | 2026-11-25 | fastReader's self-imports rewritten from `fastReader.` to `planning_system.fastreader.` (and its .sh wrapper's module path); no logic changed. Copied tests: fastReader 108/108, quick-json-reader 25/25, prompt builder 12/12 pass in place | Minimal change needed for the copy to run inside our package |
| 9 | 2026-11-25 | Copied in fastReader, quick-json-reader (without its web UI), ai-rule-builder (whole) and source-of-truth's package raw into `planning_system/`; SoT is trimmed to the capture side during the build. Origins in `planning_system/COPIED-SOURCES.md` | All four were decided as copy-ins; copying is mechanical and lets the scaffold start from real code |
| 8 | 2026-11-25 | Corrected order after user reminder: finish all specs, then scaffold (hollow modules + mocked integration tests), then build; parallel spec drafting in 4 groups (server infra; extraction + reader adaptation; clients + task flow; prompt builder + backup + web UI) | User: plan and scaffold the whole project before work churns |
| 7 | 2026-11-25 | Out of the first build: web_ui (Gradio), review_dispatch, task_assignment beyond assign+mint, database_backup, Codex | Not needed for the local Claude CLI scenario now; specs/tree unchanged |
