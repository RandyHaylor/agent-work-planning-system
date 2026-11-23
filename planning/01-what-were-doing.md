# What we're doing

Level 1. Approved by the user on 2026-11-23.

## Goal

Enable planning and scaffolding that allow long-running, unsupervised, trustworthy agent work.

User: "the top level 'what is our GOAL' which is to enable planning and scaffolding to allow long running unsupervised trustworthy agent work"

## Goals that serve it

- **Real planning for anything beyond a simple standalone request,** from a focused feature up to a broad goal, run through all the levels, that agents can work from without drifting. The user manages instead of babysitting, fixing and tweaking.
- **The user's own words as the law.** Every requirement traces back to what the user said or explicitly confirmed. Agents don't fill gaps with assumptions or paraphrase, and don't misread product vocabulary.
- **Control over what enters the plan.** Proposals come to the user as a list, and only what they approve is added.
- **Trustworthy research.** Technical claims trace back to real sources, with quotes the system guarantees are in those sources.
- **Visibility.** The user can view the whole tree, including requirements and agent notes, through the wiki, and add addendums. The tree is also the documentation of what was built.
- **Approval from anywhere.** An approval queue on the wiki for proposals from web agents, with notes that count as quotes.
- **Admin control.** Knowledge bases and which projects can see them, permissions, task assignment, and how strongly agents are isolated (the user's choice).
- **Harness freedom.** It works with Claude Code, Codex, Pi, desktop apps, web chats, or custom systems such as Unharness.

User: "the initial goals list was good, BUT it lacked the top level 'what is our GOAL'"

## Generally how

> **README synopsis.** The user marked this text block for use as the synopsis in the GitHub README.

The existing agent planning server (Postgres, served over HTTPS) grows into this system. The user plans with an agent through all the levels in one project tree: what we're doing, definition of done, high-level plan, walkthroughs, module specs, test scaffold and build. Every requirement rests on the user's own words, and every technical claim rests on a source the system itself captures. The user approves each addition. Before any build starts, the plan becomes module specs, interface definitions and types, and real integration tests run against mocked modules, all passing. The build is then split into task nodes, and work on a task is accepted only when it passes those tests. Escalations go to the user, and the user views the whole tree as the documentation, from whichever harness they use.

User: "this is great and this is a great synopsis/text block for the github readme so go ahead and mark that"

Sources: `Agent_Planning_System_Plan.md`, `Top-Down_Planning_Philosophy.md` (this folder).
