# Walkthroughs

Level 4. Approved by the user on 2026-11-23. User: "i think they seem good enough to move forward"

Each walkthrough is an independent user story: one user, one real goal, end to end. They stay high level, because they will also serve as examples, in the app's prompts, of what is expected and at what level of detail. User: "yes, stay relatively high level. we'll likely keep these user stories as real examples in prompts in the app we're building as examples of what is expected and level of detail"

The stories are also realistic, runnable end-to-end tests: final acceptance runs one, chosen at random (level 2, item 19). Steps that depend on chance are written as "if this happens, the system does this," so a run passes either way. User: "a"

## Story 1: a solo developer builds a new CLI tool

**User:** a developer working alone in Claude Code on their own machine.
**Goal:** a small command-line tool that converts their notes folder into a static site.

1. The developer starts a project from Claude Code. The local client links the session to the new project.
2. **What we're doing.** The agent asks what the tool is for, who uses it and generally how. The developer answers in conversation. The agent proposes the level 1 text, the developer says "yes", and that "yes" is captured as a quote and cited on the node.
3. **Definition of done.** The developer mentions it must run offline and stay free. The agent records these as hard constraints, quoting the developer, and the developer approves the level.
4. **High-level plan.** The agent needs to know how a markdown library handles front matter. It fetches the library's docs through the service and cites the relevant lines. If a technical question is unclear, the agent runs a spike as a task under level 3, and the result is visible there. The developer approves the plan.
5. **Review.** Each node goes to async review as it's submitted. If a node fails review, for example because its title makes a claim ("Fast incremental builds"), the agent fixes it and resubmits until it passes.
6. **Walkthroughs.** The agent writes two stories for the tool itself (first build of a site; rebuilding after one note changes). If walking them finds a missing piece, such as a file watcher, it is carried up to level 3, approved, and walked down again.
7. **Module specs.** The agent proposes modules (reading notes, rendering pages, writing the site, the CLI), using good judgement on separation. The developer adjusts one boundary and approves.
8. **Test scaffold.** Hollow modules and integration tests run against mocks, and all pass. The developer approves the scaffold.
9. **Build.** Task nodes are created and scoped worker tokens minted. Each worker sees its task plus the context story from the nodes above it, and can only turn in a response. Workers build to pass the tests.
10. **Acceptance.** Work that passes its tests is accepted. The tree now documents what was built, and the developer can read it in the wiki.

## Story 2: a developer adds a feature to an existing app, partly away from the desk

**User:** a developer maintaining a web app, using Codex at their desk and a web chat on their phone.
**Goal:** add CSV export to the app's reports page.

1. At the desk, the developer starts a project for the feature in Codex. The knowledge base holding the existing app's code and docs is exposed to the project, and the agent cites the parts that matter.
2. **What we're doing** and **definition of done** are agreed in conversation and captured as quotes. The developer is clear that exports must respect existing user permissions.
3. **High-level plan.** The agent surveys the reports code and cites it. The developer approves the plan.
4. The developer leaves. On their phone, they approve using a web chat agent, accepting that it can't capture user quotes, and continue with it over the web-facing interface. The web agent can read the tree and existing quotes, but can't capture new user quotes, so its walkthrough and module proposals go to the approval queue.
5. In the Gradio wiki, the developer approves the walkthroughs with a note ("large reports must stream, not load all at once"); the note becomes a citable quote. They reject one module proposal and add an addendum explaining why.
6. If a new quote supersedes an earlier one, for example the streaming note replacing an earlier statement that exports could load whole reports, a discrepancy task is raised for the developer, who reviews it and decides.
7. Back at the desk, specs and the test scaffold are finished in Codex and approved.
8. **Build.** If a worker can't meet its spec, for example because the permissions check it was told to reuse doesn't cover exports, it finishes what it can, escalates, and turns in its work; the node pauses and the developer is alerted.
9. The developer reviews the escalation and decides which layer needs a change, for example the high-level plan. The change is made at level 3, and each level below is re-walked on the way down. The escalation is marked resolved with notes, and the task resumes with an instruction to review it.
10. **Acceptance.** The export module is a deep module, so after its tests pass an outside agent verifies it against the original tests and definition of done. It passes, and the work is accepted.

## Story 3: a lead agent directs weaker agents

**User:** a strong agent controlling the system, directing smaller workers. From the system's point of view it is the user.
**Goal:** a data-cleanup tool for a set of messy CSV exports.

1. The lead agent is given the admin credential for the MCP-style interface. It starts a project and chooses which knowledge bases the project can see.
2. It plans through the levels with a planner agent. Its words and confirmations are the user quotes; the planner proposes and the lead agent approves each level.
3. When work is ready, task nodes are created, worker tokens minted, and workers started in their harnesses, each in its own isolated copy of the repo.
4. Workers see only their task and its context story. If a worker tries to edit its task, tests or definition of done, permissions refuse it.
5. Through the MCP-style interface, the lead agent reads the tree, reviews escalations and approves proposals, as any user would.
6. **Acceptance.** Work that passes its tests is accepted, and the planner merges it. The finished tree is the documentation of what was built.

## Gaps found (to carry up)

These came up while walking the stories.

**Answered**
1. **Existing code as a source.** Handled by knowledge bases exposed to the project. User: "we literally defined the knowledgebase system for this very situation"
2. **Merging accepted work.** The planner merges each task's work on acceptance (user's answer). To carry up to level 3.
3. **Context summaries.** The planner creating a node writes its summary, and it must be updated whenever the node is created or updated, at least its last-verified date. Carried up to level 3.
4. **An agent as "the user."** Moot: whoever controls the system is the user. User: "from our system's perspective, the entity controlling the system is the 'user' - so your question is irrelevant here and moot."

5. **Agents without quote capture.** Any agent that can use the HTTPS or local CLI interface is supported. Agents that can't support user-prompt capture (web chats, or an unsupported CLI or app) are the same case: using them forgoes the guaranteed user-quote system, is not recommended, and needs the user's approval. Such agents can still use the web approval queue. Carried up to level 3. User: "the user must approve the use of agents (web or unsupported cli/app) that cannot support the user prompt capturing transcript hooks, etc. These are the same situation. sure we can support any agent that can use the https or local cli interface, assuming the user approves the (not reccomended) forgoeing of the guranteed user quote system."

**Superseded questions**
- **Local models as workers** (story 3). Only Claude Code and Codex adapters exist at first. Are workers on other harnesses or local models in scope for this story? (level 2)
- **Web agent quotes** (story 2). Confirming that a web agent can never capture new user quotes, only queue proposals. (level 3, matches the Plan)
