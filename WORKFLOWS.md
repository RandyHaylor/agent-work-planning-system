# Who does what

Four parties. Each has one job. Nothing moves up a level without the party above saying so.

The lanes below are context control, not security. An agent that sees everything builds what it imagines. Each party is given exactly the context its job needs, and the server makes stepping outside it an explicit act. That keeps honest agents on task; it is not meant to stop a determined one.

Every agent's session begins with the blocks from `agent_instruction_injections.json` that list its type, verbatim, before its custom instructions. The party that starts the session includes them.

## User
- Approves plans, in chat, as written on the server.
- Approves knowledge base changes.
- Approves every admin session by typing the admin password into the login window. Nobody else knows it.
- Resolves roadblocks: scope changes, interface changes, contradictions, specs that cannot be built.
- Never touches the server directly.

## Admin agent
A session, not a standing role, and not required to start work. Exists only after the user types the password, dies on server restart or logout.
- Creates knowledge bases and writes their content from conversation with the user.
- Hides a project, or grants one project visibility into a hidden one.
- Reads kb proposals from projects, discusses them with the user, applies the approved ones, resolves the proposal docs.
- Does not plan projects. Does not build anything.

When a planner needs one of these, it either spawns a new unattached agent to become admin, with the user typing the password, or tells the user to start an admin session and passes on the instruction.

## Planner agent
One project, start to finish. Any agent with server access starts a project with `POST /projects` and receives that project's planner token in the response. That agent is the planner.
- Decides which knowledge bases its project uses, and may override the set on a specific task node.
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
uv run ai-project-planning-server init-env            # DB password into .env, once per machine
docker compose up -d --wait
uv run ai-project-planning-server bootstrap           # user types the admin password; writes server_access_token; nothing else printed
uv run ai-project-planning-server                     # HTTPS on 127.0.0.1:8787
```
Every request carries the contents of `server_access_token` in the `X-Server-Access` header, so only processes with local disk access reach the server. An agent then starts a project with `POST /projects` and becomes its planner. An admin session (`admin-login`, user types the password) is needed only for kb writes, hiding projects, visibility grants, and applying proposals.

## Isolation
Whether agents run in their own VMs, containers, or one shared machine is the user's and the project's decision, outside this server. Agents treat the server as the only source of project truth, plus references the planner grants explicitly and in the form given. A project that requires isolation says so in its environment doc; the planner is responsible for arranging it.

## Handoffs
| From | To | What is handed over |
|---|---|---|
| User | Admin | Injected instruction blocks for `admin`, then the skill file; a typed password in the login window, per session |
| Server | Planner | Project planner token, in the `POST /projects` response |
| Planner | Admin | A spawned admin agent, or an instruction relayed through the user, for kb writes, hiding, visibility, proposals |
| Planner | Worker | Injected instruction blocks for `worker`, then worker token, workspace path, skill file, scratch folder name |
| Worker | Planner | Report doc on the node; escalation docs when blocked |
| Planner | User | Plan text as written on the server; escalations outside scope; closure summary |
| Planner, Worker | Admin | `kb_proposal` docs |
| Admin | User | Each proposal, for approval |
