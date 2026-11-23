# Definition of done

Level 2. Approved by the user on 2026-11-23.

## Done when

1. **Projects run through all the levels in one tree.** One generic node type. Levels 1 to 4 are linear, and branching starts at module specs.
2. **Requirements live on the node they govern** and pass down to every node below.
3. **User quotes are real.** They're captured from the real conversation, and agents can never create or edit them.
4. **Document quotes are real.** The system fetches and caches every source, and serves the quoted text itself. Agents never see the cache.
5. **Nothing enters a plan without the user's approval,** including approvals made through the wiki's queue, where a note counts as a quote.
6. **Nodes are reviewed against their quotes** by reviewer clients, asynchronously, never by the agents doing the work.
7. **Every agent gets the story** of what's being built, assembled from the context summaries above its task.
8. **Workers are locked to their task.** They can turn in a response but can't change the task, its tests or its definition of done, and this is enforced by permissions.
9. **Tests decide acceptance.** Deep modules also get outside verification against the original tests.
10. **Escalations are queue events** that belong to the node that raised them, handled as recorded in `process-levels.md`.
11. **Spikes can run at any layer.**
12. **The user can view the whole tree** on the wiki and add addendums.
13. **The same interface over HTTPS and the CLI,** with a local client and harness adapters.
14. **The existing roles and permissions carry over:** tiers, knowledge bases, visibility, version history and cascading revocation.
15. **Harness adapters for Claude Code and Codex.** Others come later. User: "we're starting with claude code and codex only."
16. **Runs on the host, built so it can be reached from the web.** For now that means testing web-agent access through Cloudflare or something similar. User: "the fact that web agents can reach it implies we will be supporting web facing view. to start that will just mean we can use cloudfare for testing that function (or similar). mostly we'll just be running on the host, but must buld it right to leave doors open."
17. **A Gradio UI that is only a UI.** Every action, including the user's own actions, can be done directly through the HTTP interface and the CLI. User: "stick with gradio for the ui. It's also essential that the ui remain simply the ui, DO NOT PUT BUSINESS LOGIC IN THE WEB/GRADOI/UI CODE - REMEMBER THAT THERE'S A CLI AND HTTP INTERFACE THAT MUST DO EVERYTHING DIRECTLY - EVEN USER ACTIONS."
18. **An MCP-style interface,** so an agent given the admin credential can read and edit for the user. User: "we'll likely want to include mcp-like interface as well so an agent can read/edit/etc FOR the user if given the admin access credential"

19. **Final acceptance runs a user story.** One user story, chosen at random from the level 4 list, is run end to end on the real system. The user stories are therefore realistic, runnable end-to-end tests. User: "for the final review/acceptance task once all work is done, I think a user story is a good candidate for a run through, chose and random from the list - so the user stories should be realistic end to end tests as well."

## Hard constraints

- Built on the existing repo: Python, FastAPI, psycopg and Postgres 16.
- The source repos (source-of-truth-agent-tool, ai-agent-fastReader, quick-json-reader) are left untouched. Code is copied in and adapted.
- Every module has clear documentation, an interface, types, a definition of done and tests. It is its own package only when that makes sense; a non-package module that doesn't make sense to integration-test on its own can rely on unit tests (see `03-high-level-plan.md`). External integrations get generic strategy-style wrappers.
- Harness-agnostic: no harness-specific code outside the adapters.
- No business logic in the web, Gradio or UI code.
- The HTTP interface and the CLI can do everything, including user actions.
- Built using its own process.

Sources: `Agent_Planning_System_Plan.md`, `Top-Down_Planning_Philosophy.md`, the repo `README.md`.
