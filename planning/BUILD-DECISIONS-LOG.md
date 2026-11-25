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
| 7 | 2026-11-25 | Out of the first build: web_ui (Gradio), review_dispatch, task_assignment beyond assign+mint, database_backup, Codex | Not needed for the local Claude CLI scenario now; specs/tree unchanged |
