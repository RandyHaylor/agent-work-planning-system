# Running the new planning system (local host + Claude Code)

First usable build (2026-11-25). Plan: `BUILD-PLAN.md`. Every call made during the build: `BUILD-DECISIONS-LOG.md`. Items for you: `BUILD-ISSUES.md`.

## One-time setup

1. **Start Postgres** (repo root): `docker compose up -d --wait`
2. **Install**: `uv sync --extra test` (Node is also required, for quick-json-reader)
3. **Set your own admin password** (required: an agent saw the bootstrap one, BUILD-ISSUES #0). Type it yourself; never give it to an agent:
   `uv run planning-server set-admin-password`
   (For a brand-new database: `uv run planning-server bootstrap`, which creates the database, runs migrations and prompts for the password.)

`.env` holds `PLANNING_DSN` for the local `planning_system` database (added during the build, built from `PLANNER_DB_PASSWORD`).

## Run the server

`uv run planning-server run` serves HTTPS on `https://127.0.0.1:8788`, using the self-signed certificate in `certs/server.crt`.

## Use it (CLI: `uv run planning ...`; prints JSON, `--text` for readable output)

Environment for any client: `PLANNING_URL=https://127.0.0.1:8788`, `PLANNING_CA_CERT=<repo>/certs/server.crt`, `PLANNING_TOKEN=<token>`.

- **Admin (you, or an agent acting for you):** `planning admin login` opens a popup; you type the password; it prints a session token (the agent gets the token, never the password). `planning admin logout` ends it.
- **Projects and tree:** `planning projects create --title T --summary S`; `planning nodes create --parent ID --title T --level LABEL --summary S [--labels ...] [--depends-on ...]`; `nodes get|children|ancestors|ready|update|move|state|context|list`; `content add|replace`.
- **Tasks:** `planning task assign NODE --agent AGENT --branch B` (returns the worker token); `planning task start NODE --agent AGENT --token TOKEN --dir WORKDIR [--role worker|planner]` starts a headless Claude Code session for it; `task stop|list`.
- **Workers:** `planning supplementary create --kind tech_spike|requirement_request --title T --summary S` (placed before the worker's own task).
- **Reader (fastReader shape):** `planning load <url | file ...> [--strategy NAME]` or `planning load --search "terms"`; `toc ID`, `get ID --section N`, `search TERMS --ids ID ...`, `json ID [flags]`, `lines ID START END`, `cite ID START END` (moves the item into permanent references). `references get|lines REF`.
- **Your words as quotes:** `planning credentials quote-key --label <this machine>` (stores the key locally), then `planning client install-hooks` (adds the Claude Code UserPromptSubmit + AskUserQuestion hooks; backs up settings first). Prompts are captured to the local cache (`~/.planning-client`); `planning client exchanges` lists them; `planning cite-exchange LOCAL_ID` syncs one to the server as a reference.
- **Guidance:** `planning guidance planner|worker|admin`; `planning guidance-editor` opens the prompt-builder website to edit roles (presets) and rules.

## Enforced citations and automatic review

- Every content write needs one claim tag: `requirement` / `decision` (cite a user quote), `technical` / `documentation` (cite a loaded document), `plan` (any evidence), `note` (no citation). Citations are `[reference-id:start-end]`. Uncited claims get a 422 saying what to add.
- Each cited claim gets a review record. Start a reviewer: the planner creates a task labelled `review`, assigns it, sets it `in_progress`; then with that worker token run `planning review serve --project ID --backend local_llm|claude_code|pi [--model haiku] [--once]`.
  - `local_llm` (default): the local llama.cpp gemma4 at 127.0.0.1:8898 (shared, one slot; never start/stop it).
  - `claude_code`: headless `claude -p` (e.g. `--model haiku`; billed).
  - `pi`: our own pi harness in `tools/pi` (running it needs your OK, BUILD-ISSUES #10).
- `planning review list --project ID [--status failed]`, `planning review show REVIEW_ID`. A node can't be marked done while any of its reviews are pending or failed.
- Live check: `uv run python -I scripts/live_review_run.py [--skip-claude]`.

## Tests

`uv run --extra test python -m pytest -q tests/planning_system planning_system/prompt_builder/tests planning_system/fastreader/test` (717 passed at handover; storage tests use throwaway Postgres databases). quick-json-reader JS: `node --test planning_system/quick_json_reader/tests/test_quick_json_reader.js planning_system/quick_json_reader/tests/test_stdin_runner.js`.

Live smoke test: `uv run python -I scripts/live_smoke_test.py` (stop any server on 8788 first). It bootstraps a throwaway `planning_system_smoke` database with a throwaway admin password, starts the real HTTPS server, drives the real CLI, and drops the database. It passed: admin session, project, nodes, assign + worker token, tech spike, load, toc, search, cite, reference lines, context, guidance, quote key, and the Claude Code UserPromptSubmit hook capturing a prompt locally then `cite-exchange` syncing it as a `user_exchange` reference.

Not yet run live: `planning task start` (it starts a real, billed `claude -p` session); its test runs only with `PLANNING_RUN_CLAUDE=1`.
