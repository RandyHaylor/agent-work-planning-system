# Top-Down Planning: Philosophy

Nov 22, 2026 · @Randy Haylor

## The win

Spend an hour or two planning, in close to real time, then step away while agents work for hours without drifting or hallucinating.

- Planning produces specs built on real quotes, real technical references, real interfaces, and real tests that were built and walked through.
- With that scaffold in place, coding becomes fairly trivial and well within reach of current AI.
- The human stops babysitting, fixing and tweaking all day. They manage, and the agents work unhindered on structure that has been validated and can be trusted.

## End to end

The whole process forms one chain, from real quotes down to assigned task nodes.

1. Requirements come from real user quotes.
2. Research and documentation are proven with real quotes from sources, and validated.
3. The plan is built top-down: what we're doing, the definition of done, the high-level plan, walkthroughs, then the modules.
4. Module scaffolding and integration tests are built, and pass against mocks.
5. Task nodes are assigned and broken down further. Each agent can only turn in a response on its own task, and the tests decide whether it's accepted.

## Why

Plan all the work before any of it starts, top-down, and back every point with a real reference. The usual approach of starting from a vague idea and figuring things out along the way is the mistake. Most answers can be found before work begins. Work misses requirements that were never gathered.

- The doer, human or AI, doesn't know what's in the requester's head, or what the company does.
- Product vocabulary gets misread. Terms like "fatigue" or "attention span" have exact meanings in a given product, and an agent will guess them wrong.
- Unstated constraints get missed. "For school, on a website my friends can try, and I don't want to pay" rules out paid services before anyone suggests one.
- An agent fills gaps with assumptions and paraphrase. The result drifts from what was asked, and nobody can point to where.

## Core principles

The process is the deliverable. An end result reached without it counts as a failure.

1. **Process over speed.** Building the levels of planning and the documentation tree comes before any result. It matters more than reaching the end quickly.
2. **Top-down, one level at a time.** Finish a level before dropping to the next. Higher levels contain no lower-level detail.
3. **Every point is demonstrated.** Each requirement, decision and technical claim is backed by direct quotes that adequately support it. The sources are the user, the web, documentation, code and other references.
4. **No paraphrase as evidence.** Quotes are shown as they appear in the source, never restated by the writer. A summary is never treated as proof.
5. **Titles make no claims.** A title is a short, generic noun phrase naming a topic, such as "vendor placement". The quotes underneath carry the claims.
6. **The documentation is the system's record.** It is the plan while planning and the documentation of what was built afterward. It stays accurate as the work changes.
7. **The user is whoever is at the interface.** That could be a person, a team, or a stronger agent directing weaker ones.

**Nothing enters the plan without explicit approval.** No one adds a proposal to a formal planning doc on their own. Proposals go to the user as a list, and only items the user explicitly approves are added.

## The levels

Work moves down through seven levels in order. At each level, plan as far as possible before going down a level. Levels 1 to 4 are one node each, in a straight line. Branching starts at level 5.

```
1 What we're doing
└─ 2 Definition of done
   └─ 3 High-level plan
      └─ 4 Walkthroughs
         └─ 5 Module specs   (one node per module)
            └─ 6 Test scaffold
               └─ 7 Build
```

1. **What we're doing.** Who needs what for it to work, and generally how.
2. **Definition of done.** For the top-level goal, including the real hard requirements and constraints.
3. **High-level plan.** The whiteboard plan: the general approach and the conceptual pieces, each with its own definition of done and requirements. One node; the pieces are named inside it, not split into nodes. Repo structure is decided here based on project size and context.
4. **Walkthroughs.** One node covering the whole system: step-by-step walkthroughs of use-case scenarios and user stories, showing how the system will work. These refine the design before any scaffolding or code.
5. **Module specs.** The actual modules, which need not line up with the level 3 pieces and may be many more. For each module: interfaces, types, rules and definition of done.
6. **Test scaffold.** Mocked integration tests for every module at its interface, all passing, before real development starts. This is a formal planning layer and gets extra effort.
7. **Build.** Build to spec.

**Requirements live on the node they govern** and always pass down to every node below. They never sit in a separate branch.

**Spikes** are tasks, allowed at any layer. A spike done at a layer is visible there as information for that layer. Its findings don't pass down by default; if a spike proves something, that can be noted where it applies.

**Knowledge bases are not a level.** They are separate stores that can be exposed to a project, or not.

**Scale to the job.** The process offers clear options with fewer levels for smaller requests. The option is chosen from the scope and size of the request, so a small change doesn't carry a large project's ceremony.

## Moving back up a level

Work at any level can turn up problems that force changes higher up. Don't halt the moment that happens. Doing the rest of the work first greatly reduces thrashing.

1. Finish whatever can still be done or evaluated at the current level, and note where the issue may block some of it.
2. Carry the issue list up to the level that has to address it.
3. Review that level as a whole, and walk through it again.
4. Work back down through each level, reviewing and updating as you go.

## Backlogs

Open questions and spikes are set aside, not chased the moment they come up. Planning continues around them until it can't go further.

- **Questions backlog.** Anything that needs an answer goes on the list, and planning carries on. When planning blocks, answer the whole backlog in one batch, then continue.
- **Spike backlog.** Spikes are kept separately until they're needed. They run as tasks at whatever layer needs the answer.
- **Batch research.** Questions that need research are investigated together. Every answer comes back with quotes and links to the cached sources.

## References and evidence

Every point must link back to the exact words it rests on.

- **User input** is recorded word for word, in an append-only log. A requirement cites the user's own words or a confirmation the user gave.
- **Web and documentation sources** are cached and become part of the project. Each cached source records its URL or origin, the date it was cached, and whether references should re-check the original. The cached copy is the default. Re-check only very fast-moving sources.
- **A quote** is a pointer to a source plus a range within it. The exact text comes from the source, never from the writer's memory.
- **Large sources** are split into sections, so a quote points at the part that supports the claim, not the whole document.

* **User confirmation is required, and it counts as a quote.** A quote proves the user requested or acknowledged something. When a requirement is pieced together from a discussion, the agent asks the user to confirm it. The agent's question and the user's reply are captured together, so a plain "yes" can be cited. A native ask-question tool works too, where the harness has one.
* **Quotes come only through the system.** The service fetches and caches every source, logs its URL, and serves quotes from that cache. Agents can never see or touch the cache, so quotes are safe from hallucination, tampering and inference. An agent may say "I inferred X because of this source, and here's the quote", never "I read this, so X".

- **A reviewer agent scans every node.** Every specification or user decision must cite a user quote that states or acknowledges it. Every technical claim must cite a reference quote that corroborates it.

## Modularity and testing

Modules are kept far more separate than is typical, enough that each could stand alone as its own tool.

- Each module has its own README, interface, types, definition of done and integration tests.
- Modules interact only through documented interfaces, never through each other's internals.
- A project starts with mocked integration tests for every module, all passing at the interface level.
- Existing code is reused only where it fits a clean modular design. It never forces awkward patterns onto the new design.

* The point of separation is to contain the complexity any one worker has to handle, and to force good modular code.
* The finished product pulls the modules in as dependencies and still works seamlessly. Done right, this is always better, not worse.
* External services and dependencies are wrapped in generic, strategy-style wrappers. That makes them easier to test and replace, and leads to more reusable modules.

## Honor-system checklist

Use this list to follow the process without any tools enforcing it. The SoT tool enforces the same rules where it's in use.

- [ ] Top node states what we're doing, who needs what, and generally how
- [ ] Definition of done for the top-level goal includes the hard requirements and constraints
- [ ] Requirements sit on the node they govern, not in a separate branch
- [ ] Each level is finished before work moves to the next
- [ ] Higher levels contain no lower-level detail
- [ ] Every point has a direct quote and a source link
- [ ] No paraphrase is used as evidence
- [ ] Titles are generic topics, not claims
- [ ] Open questions and spikes are in their backlogs, and resolved in batches
- [ ] Every module has an interface, types, definition of done and integration tests
- [ ] Mocked integration tests pass for every module before development starts
- [ ] Spikes a node depends on are done before that node's work goes ahead
- [ ] Documentation matches what was actually built

* [ ] Level option chosen to fit the size and scope of the request
* [ ] Requirements pieced together from discussion have a captured user confirmation
* [ ] Use-case walkthroughs done before module specs and scaffolding
* [ ] Issues that force higher-level changes are carried up, and levels re-walked on the way back down

- [ ] Nothing in the plan was added without the user's explicit approval
