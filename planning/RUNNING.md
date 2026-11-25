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

## Tests

`uv run --extra test python -m pytest -q tests/planning_system planning_system/prompt_builder/tests planning_system/fastreader/test` (717 passed at handover; storage tests use throwaway Postgres databases). quick-json-reader JS: `node --test planning_system/quick_json_reader/tests/test_quick_json_reader.js planning_system/quick_json_reader/tests/test_stdin_runner.js`.

A live smoke test (throwaway database, real HTTPS server, real CLI) passed: admin session, project, nodes, assign + worker token, tech spike, load, toc, search, cite, reference lines, context, guidance, quote key.
