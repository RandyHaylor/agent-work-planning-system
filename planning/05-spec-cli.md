# Spec: cli (`planning` command)

DRAFT (agent-approved under the user's build handover; see BUILD-DECISIONS-LOG.md)

## Recorded decisions this builds on

- "I don't want a generated CLI. The CLI should be a very thin hand-written wrapper so agents can call the server, which is what I thought we were doing." (`05-module-specs.md`, Round 5)
- Tree v5: `cli/ very thin hand-written wrapper so agents can call the server (uses api_client)`; `entry_point`.
- "no logic in any UI"; the web UI and an admin agent use the same API (`05-module-specs.md`, Round 2 and Round 5 web_ui).
- fastReader is kept "more or less intact" with its "interactive help menu" (`05-module-specs.md`, "Reader direction change"); reader routes in `BUILD-PLAN.md`.
- "to register a reference they have to pull the URL up through the reader. Make that clear in prompting and tooling." (same section)
- The planner starts/stops tasks; supplementary tasks via one worker tool (`05-module-specs.md`, "Build handover", "Phase 2: access" 2).
- Citing a local exchange syncs it (`05-spec-quote-capture.md`).

## Module list

```
cli/
  entry_point        argparse (stdlib) subcommands; each handler = parse args -> one api_client (or local_client) call -> print JSON
  output_format      prints the server's JSON as-is (default) or `--text` for readable toc/get/search output
```

Rules: no business logic; one handler per line below; exit code 0 ok, 1 server error (message on stderr), 2 usage. Token from `PLANNING_TOKEN`, URL from `PLANNING_URL`, cert from `PLANNING_CA_CERT`. Commands marked (local) call `local_client`, not the server.

## Commands

Identity and credentials
- `planning admin login` -> admin_login popup -> `POST /admin/sessions`; prints `PLANNING_TOKEN=...`
- `planning admin logout` -> ends the admin session (route not in BUILD-PLAN; see flags)
- `planning me` -> `GET /me`
- `planning credentials mint --role R --project P [--scope N] --agent A` -> `POST /credentials`
- `planning credentials quote-key --label L` -> `POST /credentials/quote-key` (stored by client_credentials)
- `planning credentials revoke ID` -> `POST /credentials/{id}/revoke`
- `planning agents register ID [--host --platform --model --path --system --url]` -> `POST /agents`

Tree
- `planning projects create --title --summary` -> `POST /projects`
- `planning nodes create --parent --title --level --summary [--labels] [--depends-on] [--position]` -> `POST /nodes`
- `planning nodes get ID` -> `GET /nodes/{id}`
- `planning nodes children ID` -> `GET /nodes/{id}/children`
- `planning nodes ancestors ID` -> `GET /nodes/{id}/ancestors`
- `planning nodes ready ID` -> `GET /nodes/{id}/ready-children`
- `planning nodes update ID [--title --summary --labels --depends-on]` -> `PATCH /nodes/{id}`
- `planning nodes move ID --parent P --position N` -> `POST /nodes/{id}/move`
- `planning nodes state ID STATE` -> `POST /nodes/{id}/state`
- `planning nodes context ID` -> `GET /nodes/{id}/context`
- `planning content add ID --text|--file [--tags]` -> `POST /nodes/{id}/content`
- `planning content replace ID REF --text|--file` -> `PUT /nodes/{id}/content/{reference_id}`
- `planning supplementary create --kind tech_spike|requirement_request --title --summary` -> `POST /nodes/{own task}/supplementary` (worker; task id from `GET /me`)

Tasks (planner)
- `planning task assign ID --agent A --branch B` -> `POST /nodes/{id}/assign`; prints node + worker token
- `planning task start ID --agent A --token T --dir D [--role worker|planner]` (local) -> session runner; reads `GET /guidance/{role}` + `GET /nodes/{id}/context`
- `planning task stop A` (local) -> terminates the session
- `planning task list` (local) -> sessions this client started and whether alive
- `planning review ask "question" [--context PATH...]` (local) -> review_worker

Reader (fastReader's shape)
- `planning load URL|FILE|--search "terms" [--strategy S] [--line-start --line-count]` -> `POST /reader/load`
- `planning toc ID` -> `GET /reader/{id}/toc`
- `planning get ID [section/line args as fastReader]` -> `GET /reader/{id}/get`
- `planning search TERMS [--ids ...]` -> `POST /reader/search`
- `planning json ID [quick-json-reader flags]` -> `POST /reader/{id}/json`
- `planning lines ID START END` -> `GET /reader/{id}/lines`
- `planning cite ID START END` -> `POST /reader/cite`
- `planning cite-exchange LOCAL_ID` (local) -> ReferenceSync -> `POST /references/user-exchange`
- `planning help [command]` -> fastReader's help text, adapted

References
- `planning references get ID [--follow-superseded]` -> `GET /references/{id}`
- `planning references lines ID [--start --end]` -> `GET /references/{id}/lines`
- `planning references render CITATION` -> `POST /references/render`

Guidance
- `planning guidance ROLE` -> `GET /guidance/{role}`
- `planning guidance templates` / `planning guidance rules` -> `GET /guidance/templates`, `/guidance/rules`
- `planning guidance-editor` (local) -> launches prompt_builder's website

Local client setup
- `planning client install-hooks` (local) -> Claude Code installer (SoT `install.py`)
- `planning client exchanges [--last N]` (local) -> lists local cache exchanges with local ids

## External integration tests (api_client and local_client mocked)

1. Each server command calls exactly one api_client method with the parsed arguments and prints its JSON.
2. Contract errors exit 1 with the message on stderr; bad usage exits 2.
3. Missing `PLANNING_TOKEN` on an authenticated command fails before any request.
4. `cite-exchange` calls ReferenceSync and nothing else.
5. `load FILE` sends the file's bytes; `load URL` sends the URL.
6. No command contains branching on roles or states (grep-level check: handlers only map args to one call).
