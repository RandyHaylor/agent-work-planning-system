# Build issues for the user (review at the end)

Collected during the build instead of stopping (user: "noting any issues to address for the end").

0. **CLOSED 2026-11-28 by the user: "the admin password is not critical here not a concern".** (Was: set your own admin password before use.) During the build, an agent ran `planning-server bootstrap` with a generated admin password, so an agent has seen the current one (it was never committed). That breaks "a password only they know". Run `uv run planning-server set-admin-password` yourself and type a new one. Agents must never set or see it again (rule added to the build log, #42).
1. `agent_instruction_injections.json` (copied as-is into guidance) still uses old-server wording: workorders, `kb_proposal`, "the reference run", and repeats rules that are now rule categories. Needs your review.
2. Knowledge bases are deferred out of the first build (log #16).
3. web_ui, database_backup, Codex adapter: out of the first build (log #7).
10. **pi reviewer backend needs your OK to run.** pi (`@earendil-works/pi-coding-agent` 1.6.1, MIT) is installed locally in `tools/pi` with its own config in `tools/pi/agent` (pointed at the local llama.cpp gemma4). Running it was blocked as unreviewed third-party code. If you want it live, allow running `node tools/pi/node_modules/@earendil-works/pi-coding-agent/dist/cli.js` (or install pi yourself); the `local_llm` backend calls the same model directly and works now.
7. `planning task start` (real headless `claude -p` session) has not been run live: it's a billed run, so it waits for your go. Its test: `PLANNING_RUN_CLAUDE=1 uv run --extra test python -m pytest tests/planning_system/local_client -q`.
8. Small output inconsistency: `planning cite-exchange` prints the bare reference id, while other commands print JSON objects.
9. New nodes (including projects) start in state "assigned" (the only non-terminal start state in the approved states), even before anyone is assigned.
5. Round 4.3 said raw bytes are kept for reference; the first build stores only their hash (log #24).
6. ~~json-source-map license~~ Resolved (log #31): PyPI classifier Apache Software License; last release 1.0.5 on 2022-12-20 (not actively maintained, small pure-Python library). Used anyway; FYI only.
4. `process-levels.md` says questions go to a backlog "asked in batches" and also "one at a time"; the guidance uses the existing batch-questions rule that combines both.
