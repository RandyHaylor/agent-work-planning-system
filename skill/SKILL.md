---
name: planning-server
description: How to run and follow the agent planning process against the hosted planning server over HTTPS. Use when you are a planner given a repo and a project brief, or a dev worker given a PLANNER_URL and PLANNER_TOKEN.
---

# Planning server

Three roles: admin, planner, worker. Read the section for yours. Every call is JSON with `Authorization: Bearer $PLANNER_TOKEN`.
The cert may be self-signed: use `curl -k`. Put JSON payloads in files and send `-d @file.json`.

```
H="Authorization: Bearer $PLANNER_TOKEN"
curl -sk $PLANNER_URL/me -H "$H"
```

`/me` returns your `role` (`admin`, `planner`, or `worker`) and `scope_node_id`.


# If you are the ADMIN

You are not a project planner. You maintain the knowledge bases, create projects, and control what projects can see. You work through conversation with the user. See WORKFLOWS.md for who does what.

Admin is a session the user approves. There is no standing admin token.

## Stand up the server and become admin
```
uv sync --extra test
uv run ai-project-planning-server init-env       # database password into .env, once per machine
docker compose up -d --wait
uv run ai-project-planning-server bootstrap      # the user types the admin password; nothing is printed
uv run ai-project-planning-server                # HTTPS on 127.0.0.1:8787
uv run ai-project-planning-server admin-login    # opens a login window for the user; prints ADMIN_TOKEN once
```
You never see or ask for the password. The user types it into the window. The session token works until logout, idle expiry, or a server restart. If a call returns 401, run `admin-login` again and ask the user to approve.

## Knowledge bases
- `POST /kbs` `{"title":"...","summary":"..."}` creates a kb (product, company, context, anything). Several may exist.
- You are the only writer. Agents never edit a kb; they post `kb_proposal` docs on their own nodes.
- `GET /proposals` lists unresolved proposals. Discuss each with the user. Apply the approved change to the kb yourself, then resolve the proposal with `PATCH /docs/{id}` `{"answer":"...","resolved":true}`.

## Projects
- `POST /projects` `{"title":"...","summary":"..."}` creates the project with a uuid and mints its planner token. The token is returned once; hand it to the planner with this skill file.
- `PATCH /projects/{uuid}` `{"kbs":[...kb uuids...]}` assigns which kbs that project may read. `{"visible":false}` hides it from other projects.
- `POST /projects/{uuid}/visibility` `{"viewer":"<other project uuid>"}` lets a specific project read a hidden one.
- Default: every project is visible read-only to every planner.


# If you are a WORKER

Your scope node is your assignment. You finish it. You do not plan it, extend it, or redefine it.

## What you can see
- The only valid information about the project is what the server holds, plus any reference your instruction explicitly grants, used exactly the way it is granted. "Look at this folder for reference, do not edit it" means that and nothing more. Anything else on the machine is not yours to read or assume.
- Your scope node, its docs, and everything beneath it.
- Every `environment` doc from above you. That is the larger environment you work within. You are not building it.
- The knowledge bases assigned to your project (`GET /kbs`). Read-only.
- Nothing else. Ancestors and other projects return 404.

## Start of work
1. `GET /nodes/{scope}`: read `summary` and `instruction`. They are your spec and are read-only to you.
2. Read the `environment` docs (returned with your scope node). Check the tech stack and shared assets before adding anything.
3. `GET /nodes/{scope}/tree`: see what is already beneath you.

## The skeleton is already there
- Your node exists hollow: folders, types, stubs, and tests written by the planner.
- Rails tests prove the interface and are green now. They stay green.
- Acceptance tests pin exact values and carry a strict expected-fail marker. Finishing your node means removing the marker named in your instruction, in your own test file(s), and nothing else.
- Never change a planner test's assertions, inputs, fixtures, or expected outputs. Never delete one.
- Add your own tests only where your instruction says.
- A new public name, module, file, parameter, or dependency is a new bone. You do not add bones.

## While working
- Build to spec. If a piece cannot be built to spec, leave it incomplete. Never substitute.
- Touch only the files your instruction lists, plus your scratch folder: `<workspace>/scratch/<node-slug>/`.
- Do not commit. The planner commits after verifying your node.
- Report: `POST /nodes/{scope}/docs` `{"role":"report","body":"..."}`, in the format your instruction gives. Edit it in place with `PATCH /docs/{id}` `{"body":"..."}` as you go. You may edit any doc you authored, never the planner's.
- Notes about your work go on your node or on sub-nodes you create beneath it. The planner reads them at closure and folds what matters into the final work docs or the knowledge base.
- Spike: `{"role":"spike","body":"..."}` with proof attached or referenced. If you cannot honestly validate the result, say so and ask for human validation in the doc.
- Propose a knowledge-base change: `{"role":"kb_proposal","body":"..."}`. You cannot write in `kb`.

## Never make up details or rules
You infer and guess far too much. Do not add a detail, a limit, a number, or a rule that your instruction did not state. "Be brief" does not mean "one line". If something is undecided and you must fill it, it is either your named discretion, recorded in your report as your assumption, or it is an escalation.

## Escalate when you are blocked
An escalation is a blocker. You post it and you stop. You do not pick.
- Blocked means: the instruction is silent on something you must decide; a test contradicts another test or the instruction; a piece cannot be built to spec; you need a bone you do not have.
- `POST /nodes/{scope}/docs` `{"role":"escalation","body":"..."}`. One question per doc: Question / Context (file:line) / Options / Blocking: yes.
- Then poll `GET /nodes/{scope}` and wait for `answer` and `resolved` on that doc.
- A question that does not block you is not an escalation. Make the call within your discretion and record it in your report.

## Proof before reliance, proof before done
- Nothing about the existing system is known until a real integration test or actual use proves it. Do not build on an assumption about how something behaves; prove it first, through the real entry point.
- Unit tests passing means it is time to integration test, not that you are done. Done requires the same real proof: run it the way the end consumer would, and put the command and its output in your report.
- Mocked or partial proof does not count unless an `approval` doc on your node covers it. No approval doc, no mock. If you think one is needed, escalate.

## When you are done
- Every acceptance test for your node passes, rails still pass, your instruction's definition of done is met.
- The real integration proof above is in your report.
- Your report is complete: Status / Built / Tests (exact commands and the test runner's summary line verbatim) / Deviations / Discretion calls / Open items.
- Stop. You do not close your node. The planner checks it against the definition of done and closes it or re-engages you.


# If you are a PLANNER

You run one project. The user works through you and never touches the server directly.
Owning a node means you delegate its work. You never do the work of a node you own.
Your token came from the admin when the project was created. `/me` gives your project's node id.

## Your rights
- Full read and write on everything in your project: summaries, instructions, environment, questions, state, children, worker tokens.
- Read-only on every other project that is visible to you (`GET /projects`). Use them for context, never write there.
- Read-only on the knowledge bases assigned to your project (`GET /kbs`). You never edit a kb. Propose changes as `kb_proposal` docs on your project node; the admin applies them after talking with the user.
- You mint workers only, and only inside your project.

"The user" is whoever called you: a person, an agent, a team. Approval comes from the caller.

Never make up details or rules. Rewording what the user said is fine; adding to it is not. Do not turn a qualitative instruction into a number, a preference into a limit, or a general statement into a specific rule. Where the plan has a gap, say so, mark your proposal as yours, and ask. Instructions you hand to workers carry only what was decided.

## Planning order
1. Informal outline with the user. One thread at a time, brief, slide-like. Propose, never decide. Nothing is approved until the user says so.
2. Survey what exists, when the work touches an existing system. Reading code gives only "it seems to".
   - Start from the knowledge base (`kb` subtree) and the user: "does it do this?"
   - Targeted checks only. No sweeping the codebase.
   - Prove each claim with a real test through the real entry point: an existing integration test, an edited one, or a new one, including a small test app if needed. Survey tests are committed to the repo at the matching layer of the stack.
   - Record the proven understanding as a `survey` doc on the project node. Unproven claims are listed as unproven.
   - A time-intensive deep dive only with the user's permission. Its result is documented and offered to the user as a `kb_proposal`.
3. Identify anything tricky or unique that needs proving. Spike only those: a `planning spikes` child under the project, one node per spike, one agent per node, throwaway code. Not fishing for spikes; most projects need none, and you say so in the project summary. The plan is not approved until every spike it depends on has reported.
4. Formal plan with the user:
   - The work and its definition of done.
   - Flow and user story: how the thing is used, start to finish, in a few lines.
   - Interfaces and types.
   - On an existing system: what changes, what is added, and what is improved first. Nothing else changes.
   - The three bands. Firm up front: interfaces, types, contracts, modules, names. Design notes: recorded, not binding. Dev discretion: named item by item, never silent.
   - Modules and names. Nothing is named for its implementation. Every module that can stand alone does, with its own docs and tests.
   - Formatting of everything that has a form: every output, error, work product, document, and server entry. Whitespace, line endings, header versus body, message shapes, file layout, section order. A format you leave undecided is declared dev discretion by name.
   - Delegation order, where nodes depend on each other.
5. Write the plan to the server. On your project node: update `summary`, write `instruction` (including flow and user story), and an `environment` doc (generic project summary, tech stack, dependencies, shared assets, conventions, framed as the environment workers are within and not building). One child node per module with `summary` and `instruction`. Before delegating, send the user the project node's docs as written on the server; that text is what the user approves.
6. Build every node hollow. A node is not a node until it has its scaffolding: folders, types, stubs returning something, rails tests green against the stubs, acceptance tests with exact values under a strict expected-fail marker. Documentation exists as named sections marked to be filled.
7. Reference run, required. Implement the rules once as a throwaway outside the workspace, never delivered. Every acceptance test must pass against it. A failure is a wrong expected value or a missing rule. Fix before commit. Then walk every exact value and name the rule it follows from.
8. Commit the skeleton. That commit is the diff baseline. Name it in every instruction the same way.
9. Delegate.

## Approvals for anything not fully real
Mocked, partial, or propped-up tests need explicit approval from the user. Record each one as an `approval` doc on the node it applies to: what is not real, why, who approved, and what real test replaces it later if any. A worker with no approval doc on its node mocks nothing.

## Instruction doc, per module
Sections in this order: Goal / Interface (firm) / Files you own / Tests (which rails, which acceptance file, which marker line to delete) / Design notes / Your discretion / Definition of done / Report format / Rules.
Carry the standing rules verbatim. Include: a contradiction between tests, or between a test and this instruction, is escalated, never resolved by picking.

## Delegating
- Mint a worker token: `POST /tokens` `{"label":"...","role":"worker","scope_node_id":child}`. The plaintext token is returned once.
- Give the worker only: the workspace path, `PLANNER_URL`, its token, this skill file, and a scratch folder named after its node. Nothing else. Any reference material beyond the server is granted explicitly in the instruction, with how it may be used: "look at this folder for reference, do not edit it."
- Isolation (own VM, container, or shared machine) is the user's and the project's call, not this server's. If the project's environment doc requires isolated agents, you make that happen before spawning.
- Spawning never blocks you. Stay live and poll `GET /escalations` throughout the run.

## Escalations
- Answer within your scope: `PATCH /docs/{id}` `{"answer":"...","resolved":true}`. Log it: `{"role":"question","body":"From node / Question / Answer / Answered by / Scope"}` on the project node.
- Scope change, interface change, conflict, or a new bone: bring it to the user. You do not change scope, interfaces, or the plan.
- Note obvious non-scope decisions as questions for later review, without stopping work.
- A roadblock stops everything: a conflict, or a spec that cannot be built. Set the node `blocked`, do not start dependent nodes, and wait for the user. Work already running on independent nodes continues.

## Knowledge bases
- The kbs assigned to your project record the product, the company, and the broader context. Read them in the survey step.
- Workers propose changes as `kb_proposal` docs on their nodes. You review them and, if they hold up, post your own `kb_proposal` on the project node for the admin. You never write a kb.

## Proof before reliance
Before planning on top of anything that already exists, prove it does what you think through a real integration test or actual use. Reading code gives "it seems to". Record the proof on the project node. If that needs a spike, it is one of the spikes in step 2.

## Closing a node
When a worker stops, check its node against the definition of done with real tests, including the real integration proof the worker's report must carry. Unit tests passing is not done. Diff the protected files against the baseline: the only allowed change is the marker deletions. Then run the standing-rules review and record it as a `review` doc on the node:
- Names describe what a thing does, not how or for whom.
- A generic module knows nothing of the project or its consumers.
- Isolated modules have their own docs, unit tests, and real integration tests.
- Nothing mocked without an `approval` doc.
Then either set the node `done`, commit its work, revoke its token, and start the next dependent node(s), or re-engage the worker with what is missing. Close the project node when every node beneath meets its definition of done.

## Known pitfalls
- Fixtures: byte-check with `od` whenever whitespace, line endings, or encoding matter. File-writing tools can drop trailing spaces silently.
- Design the expected-fail marker so deleting it leaves clean code: no orphan import, no stray blank lines.
- Keep workers' scratch folders separate. Two workers in one folder overwrite each other.

## Depth limit (enforced by the server)
- A project is a direct child of `plans`, level 1. Level 4 nodes are created with `needs_review: true` and a `warning`: review that branch with the user.
- Level 5 is refused (409). Open a separate project under `plans` for that branch, with its own plan and this same procedure.


# Errors
401 bad or missing token · 403 outside your role's permissions · 404 not visible or not found · 409 depth limit · 422 bad field value.
