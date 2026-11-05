---
name: planning-server
description: How an agent uses the hosted planning tree over HTTPS. Use when you are given a PLANNER_URL and PLANNER_TOKEN and told to work from, report to, or escalate through the planning server.
---

# Planning server

You have `PLANNER_URL` (e.g. `https://host:8787`) and `PLANNER_TOKEN`. Every call is JSON with
`Authorization: Bearer $PLANNER_TOKEN`. The cert may be self-signed; use `curl -k`.

```
H="Authorization: Bearer $PLANNER_TOKEN"
curl -sk $PLANNER_URL/me -H "$H"
```

## Your scope
- `/me` tells you `scope_node_id`. That node is your assignment.
- You can read that node, everything beneath it, every ancestor, and the `kb` subtree. Nothing else (404).
- Your scope node's `summary` and `instruction` docs are read-only to you. They are your spec. Never try to change them.

## Start of work
1. `GET /nodes/{scope}` — read summary, instruction, existing docs, children.
2. `GET /nodes/{scope}/tree` — see what is already beneath you.
3. Walk ancestors (`parent_id`) and read `kb` children only as far as you need.

## While working
- Report: `POST /nodes/{scope}/docs` `{"role":"report","body":"..."}`. Edit your own doc with `PATCH /docs/{id}` `{"body":"..."}`.
- Escalate (question, blocker, spec conflict): `POST /nodes/{scope}/docs` `{"role":"escalation","body":"..."}`.
  Then poll `GET /nodes/{scope}` and watch that doc's `answer` / `resolved`. Scope or interface conflicts: stop and wait.
- Propose a knowledge-base change: `{"role":"kb_proposal","body":"..."}` on your scope node. You cannot write in `kb`.
- Sub-work you plan: `POST /nodes` `{"parent_id":scope,"title":"...","summary":"..."}`. You own it: write its `instruction`,
  and if your token has `can_spawn`, mint a child token: `POST /tokens` `{"label":"...","scope_node_id":child,"can_spawn":false}`.
  The plaintext token is returned once. Owning a node means you delegate it, you do not do its work.
- Node state: `PATCH /nodes/{id}` `{"state":"open|blocked|done"}` on nodes you own.

## Depth limit (enforced by the server)
- A project is a direct child of `plans` (level 1). Level 4 nodes are created with `needs_review: true` and the response carries a `warning`: review that branch with the user.
- Level 5 is refused (409). Open a separate project under `plans` for that branch, with its own plan and the same procedure.

## Tech spikes (convention, role `spike`)
- `POST /nodes/{id}/docs` `{"role":"spike","body":"..."}`. Same write rule as `report`.
- Spikes that inform architectural decisions attach at the project's top-level node and are coordinated with the user.
- Before building a large chunk on any platform, a small spike proving the platform is required. Example: a spinning 3D hello-world text running in three.js on the planned stack.
- Proof is demonstrated: attach or reference screenshots in the spike doc. Where you cannot honestly validate the result (video, motion, feel), ask for human validation in the spike doc and say so.

## If you are a parent / planner
- `GET /escalations` — unresolved escalations in your subtree.
- Answer: `PATCH /docs/{id}` `{"answer":"...","resolved":true}` (owner of that node only).
- Log questions for the audit trail: `{"role":"question","body":"..."}` on the node you own.
- Revoke a token you minted: `DELETE /tokens/{id}`.

## Errors
401 bad/missing token · 403 outside your permissions · 404 not visible or not found · 422 bad field value.
