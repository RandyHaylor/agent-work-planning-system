# Build issues for the user (review at the end)

Collected during the build instead of stopping (user: "noting any issues to address for the end").

1. `agent_instruction_injections.json` (copied as-is into guidance) still uses old-server wording: workorders, `kb_proposal`, "the reference run", and repeats rules that are now rule categories. Needs your review.
2. Knowledge bases are deferred out of the first build (log #16).
3. web_ui, database_backup, Codex adapter: out of the first build (log #7).
5. Round 4.3 said raw bytes are kept for reference; the first build stores only their hash (log #24).
6. quick-json-reader line mapping depends on the `json-source-map` package; its license and maintenance must be checked before level 7 uses it.
4. `process-levels.md` says questions go to a backlog "asked in batches" and also "one at a time"; the guidance uses the existing batch-questions rule that combines both.
