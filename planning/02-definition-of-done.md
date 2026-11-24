# Definition of done

Level 2. Approved by the user on 2026-11-23.

## Done when

1. **Projects run through all the levels in one tree.** One generic node type. Levels 1 to 4 are linear, and branching starts at module specs.
2. **Requirements live on the node they govern.** What passes down to every node below is a generic context block, not requirements (corrected at level 5; see `05-module-specs.md`).
3. **User quotes are real.** They're captured from the real conversation, and agents can never create or edit them.
4. **Document quotes are real.** The system fetches and caches every source, and serves the quoted text itself. Agents read only their own temp cache (through the reader) and the references visible to them; they never supply quote text (corrected at level 5).
5. **Nothing enters a plan without the user's approval,** including approvals of agent proposals made on the website (for harnesses that can't capture quotes), where a note counts as a quote.
6. **Review is a task, not a node state.** Review tasks check work against its quotes; they are run by reviewer clients, asynchronously, never by the agents doing the work (corrected at level 5).
7. **Every agent gets the story** of what's being built, assembled from the context summaries above its task.
8. **Workers are locked to their task.** They can turn in a response but can't change the task, its tests or its definition of done, and this is enforced by permissions.
9. **Tests decide acceptance.** Deep modules also get outside verification against the original tests.
10. **Escalations are tasks:** a work task that needs to escalate creates a sibling task placed before itself, so flow moves there first and returns when it's done; tech spikes use the same mechanism (corrected at level 5; see `process-levels.md`).
11. **Spikes can run at any layer.**
12. **The user can view the whole tree** on the wiki and add addendums.
13. **The same interface over HTTPS and the CLI,** with a local client and harness adapters.
14. **The existing roles and permissions carry over:** tiers, knowledge bases, visibility, version history and cascading revocation.
15. **Harness adapters: Claude Code in v1,** behind an interface so Codex and others connect later (corrected at level 5; user: "lets take codex off the table but PLEASE build it with an interface so we can connect codex later"). Earlier: "we're starting with claude code and codex only."
16. **Runs on the host, built so it can be reached from the web.** For now that means testing web-agent access through Cloudflare or something similar. User: "the fact that web agents can reach it implies we will be supporting web facing view. to start that will just mean we can use cloudfare for testing that function (or similar). mostly we'll just be running on the host, but must buld it right to leave doors open."
17. **A Gradio UI that is only a UI.** Every action, including the user's own actions, can be done directly through the HTTP interface and the CLI. User: "stick with gradio for the ui. It's also essential that the ui remain simply the ui, DO NOT PUT BUSINESS LOGIC IN THE WEB/GRADOI/UI CODE - REMEMBER THAT THERE'S A CLI AND HTTP INTERFACE THAT MUST DO EVERYTHING DIRECTLY - EVEN USER ACTIONS."
18. **An agent can act as the user.** No separate MCP server: the HTTPS interface is already agent-first. A permission level lets an agent do every action the user could do in the web interface, and more. (Refined at level 5. User: "our https interface is already LIKE a mcp server, so we don't need a separate mcp server - our tool is literally already an ai agent first tool! we simply need a permission level that allows an agent to act as a user - do all actions the user could do in the web interface and more. one more reason to have the web interface not contain business logic AT ALL") User: "we'll likely want to include mcp-like interface as well so an agent can read/edit/etc FOR the user if given the admin access credential"

19. **Final acceptance runs a user story.** One user story, chosen at random from the level 4 list, is run end to end on the real system. The user stories are therefore realistic, runnable end-to-end tests. User: "for the final review/acceptance task once all work is done, I think a user story is a good candidate for a run through, chose and random from the list - so the user stories should be realistic end to end tests as well."

20. **The system teaches its own design rules.** Its agent prompting and the contents of its docs carry the module and design rules: module separations chosen for good architecture and encapsulation, not by subject matter or upstream need lists; proven patterns only where they add value; nesting over sibling sprawl; tried-and-true design (SOLID, maintainable, sensible, readable); and no reinventing wheels. User: "this MUST inform the system itself and prompting we add (and contents of the docs as well)."

## Hard constraints

- Built on the existing repo: Python, FastAPI, psycopg and Postgres 16.
- The source repos (source-of-truth-agent-tool, ai-agent-fastReader, quick-json-reader) are left untouched. Code is copied in and adapted.
- Every module has clear documentation, an interface, types, a definition of done and tests. It is its own package only when that makes sense; a non-package module that doesn't make sense to integration-test on its own can rely on unit tests (see `03-high-level-plan.md`). External integrations get generic strategy-style wrappers.
- Harness-agnostic: no harness-specific code outside the adapters.
- No business logic in the web, Gradio or UI code.
- The HTTP interface and the CLI can do everything, including user actions.
- Built using its own process.

Sources: `Agent_Planning_System_Plan.md`, `Top-Down_Planning_Philosophy.md`, the repo `README.md`.
