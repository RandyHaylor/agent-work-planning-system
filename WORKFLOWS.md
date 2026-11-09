# Who does what

Four parties. Each has one job. Nothing moves up a level without the party above saying so.

## User
- Approves plans, in chat, as written on the server.
- Approves knowledge base changes.
- Approves every admin session by typing the admin password into the login window. Nobody else knows it.
- Resolves roadblocks: scope changes, interface changes, contradictions, specs that cannot be built.
- Never touches the server directly.

## Admin agent
A session, not a standing role. Exists only after the user types the password, dies on server restart or logout.
- Creates knowledge bases and writes their content from conversation with the user.
- Creates projects. Each creation mints that project's planner token, which the admin hands to the planner with the skill file.
- Assigns which kbs a project may read.
- Hides a project, or grants one project visibility into a hidden one.
- Reads kb proposals from projects, discusses them with the user, applies the approved ones, resolves the proposal docs.
- Does not plan projects. Does not build anything.

## Planner agent
One project, start to finish, holding that project's planner token.
- Outlines with the user, surveys what exists, runs spikes only for what must be proven.
- Writes the formal plan with the user and puts it on the server; the user approves the server text.
- Builds the hollow skeleton, proves it with the reference run, commits the baseline.
- Mints one worker token per node and hands each worker only its token, the workspace path, and the skill file.
- Answers escalations within scope, escalates the rest to the user, logs every question.
- Verifies each finished node against the definition of done with real tests, runs the standing-rules review, closes or re-engages.
- Reads other visible projects and the assigned kbs for context. Writes only in its own project. Never writes a kb; proposes.

## Worker agent
One node, holding that node's worker token.
- Reads its node, what is beneath it, the environment docs above it, and the assigned kbs.
- Finishes the hollow node to its definition of done. Removes only its own test markers.
- Writes its report, notes, spikes, and kb proposals on its node and beneath. Never edits the planner's docs.
- Escalates when blocked and stops. Never picks.
- Stops when done. Does not close its node.

## Startup, in order
```
uv run python -m server init-env            # DB password into .env, once per machine
docker compose up -d --wait
uv run python -m server bootstrap           # user types the admin password; nothing is printed
uv run python -m server                     # HTTPS on 127.0.0.1:8787
uv run python -m server admin-login         # opens the login window; user types the password; prints ADMIN_TOKEN once
```
The admin session then creates kbs and projects. Each project's planner token comes back from project creation.

## Isolation
Whether agents run in their own VMs, containers, or one shared machine is the user's and the project's decision, outside this server. Agents treat the server as the only source of project truth, plus references the planner grants explicitly and in the form given. A project that requires isolation says so in its environment doc; the planner is responsible for arranging it.

## Handoffs
| From | To | What is handed over |
|---|---|---|
| User | Admin | A typed password in the login window, per session |
| Admin | Planner | Project planner token, skill file |
| Planner | Worker | Worker token, workspace path, skill file, scratch folder name |
| Worker | Planner | Report doc on the node; escalation docs when blocked |
| Planner | User | Plan text as written on the server; escalations outside scope; closure summary |
| Planner, Worker | Admin | `kb_proposal` docs |
| Admin | User | Each proposal, for approval |
