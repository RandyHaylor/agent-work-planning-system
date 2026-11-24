# Process levels

Agreed with the user on 2026-11-22. This replaces the 8 levels in the Philosophy doc ("Top-Down Planning: Philosophy", Nov 22, 2026) for this project.

## Levels

```
1 What we're doing
└─ 2 Definition of done
   └─ 3 High-level plan  (one node; names the pieces inside it)
      └─ 4 Walkthroughs  (one node; whole system)
         └─ 5 Module specs  ← first branching: one node per module
            └─ 6 Test scaffold (per module)
               └─ 7 Build (task nodes per module)
```

Spike tasks can hang off any layer.

1. **What we're doing.** User: "the top level is 'what are we doing - who needs what to work and generally, how'"
   - The "who" is the user of the system and anyone involved in using the thing being produced, not the agents assigned the work. User: "the 'who' did not include the to be spawned worker agents, only the user of this system and any parties involved in use of the actual thing being produced. the agents assigned work are not the 'who' in this scenario"
2. **Definition of done.** User: "'definition of done' and include real hard requirements/constraints/etc for the top level goal"
3. **High-level plan.** User: "big pieces needs to be more formally the whiteboard plan or high level plan to indicate that it's more than just big pieces"; "big pieces also include dod, requirements, for them"; "the high level plan identifies the pieces ... there's no reason the high level plan would be split into nodes"
   - **Spikes** are tasks. User: "spikes should be honestly performed as tasks". They are allowed at any layer, and a spike done at a layer is visible there as information for that layer. User: "spikes should actually be allowed at any layer, but if they are done at a layer, they are visible at that layer as info for the layer". Spike findings do not pass down by default. User: "the spikes findings are not included by default. if they prove something then it can be noted/shown but if it's just there it doesn't gurantee it's relevant"
4. **Walkthroughs.** One node. User: "walkthorughs are whole system, not per module/part"
5. **Module specs.** Module separations MUST be chosen for good software architecture and encapsulation, NOT necessarily by subject matter or by upstream lists of project needs. User: "modules seperations MUST be chosen for good software architecture and encapsulation and NOT necessarily by subject matter or upstream project need lists/etc." Prioritize good, proven software engineering patterns (strategy, adapter, facade, factory, etc.), but not for their own sake: only where they add efficiency and value and reduce or encapsulate complexity. User: "we need to add to prioritize using good proven software engineering patterns, strategy, adapter, facade, factory, etc - but not just FOR THE SAKE OF IT - where it ADDS EFFICIENCY AND VALUE AND REDUCES OR ENCAPSULATES COMPLEXITY" Nest modules where it makes sense instead of making many sibling modules with cross-dependencies; lean on tried-and-true software design: SOLID, maintainable, sensible, readable. User: "rather htan try and make a bunch o fsibling modules - do NOT fight nestingmodules where it makes sense. ... I'm not trying to reinvent software design - i'm trying to LEAN ON TRIED AND TRUE SOFTWARE DESIGN - SOLID/MAINTAINABLE/SENSIBLE/READABLE" Don't reinvent wheels: always research common patterns that meet the need, and use out-of-the-box code or build conventional patterns where that makes sense. User: "we also need to stress not reinventing wheels - always research for common patterns meeting our needs and use out of the box code or build conventional patterns where that makes sense." These software-design rules must also inform the system itself: its prompting and the contents of its docs. User: "this MUST inform the system itself and prompting we add (and contents of the docs as well)." Level 5 requires many technical choices that may not have been made yet, and they must involve the user. Work in rounds: come up with questions, have them answered, do research and initial design, come up with the next round of questions, and repeat. Questions are asked one at a time, in the order that makes the most sense, using an ask-user-question tool with multiple-choice options where that is possible and makes sense. User: "instructions need to say that the questions are asked one at a time, in the order that makes the most sense, using an ask user question tool with multiple choice options where it is possible and mkes snese" User: "it needs to be clear that level 5 requires making a lot of technical choices that may not have been made to this point. that must involve the user, so instructions for level 5 must specify 'come up with questions, have them answered, do research and initial design, come up with next round of requestions, repeat'" Level 5 runs in two phases. First, walk through the entire module plan at the boundary level (each module's responsibility, nesting and dependencies) until every module is approved. Only then write types and public interfaces, module by module. User: "It seems like we slipped from planning to writing interfaces too soon. I feel like it should formally require walking through the entire high level plan before going through and wirting types/interfaces" Also, user: "the module specs will be modules that might not line up with big pieces from level 3 which is more conceptual. there may be many more modules than big pieces."
6. **Test scaffold.**
7. **Build.**

Levels 1 to 4 form a straight line, and branching starts at level 5. User: "yes I like this. benefits include going up teh layers where there are issues/planning."

## Module design (level 5 and all code)

Approved by the user 2026-11-23. These shape this project AND the system's own prompting and docs. User: "we need some commandments or something, as well as optoins for approaches."

### Commandments (adhere to these strongly)

1. **Separate modules well for whatever paradigm fits the approach.** User: "Modules need - good separation for whatever paradigm is fitting the aproach"
2. **Cohesion decides what goes together:** things that belong together mechanically, never a shared subject, audience or label. User: "cohesion in module separation approach"
3. **Don't shy away from small modules.** User: "Do NOT shy away from small modules - if a small module makes sense, then it's a small module."
4. **Nest modules where appropriate,** especially to break up larger modules. User: "nesting modules where appropriate (especially to break up larger modules)"
5. **List every module, small and big.** User: "Small modules can be grouped into bigger modules, that doens't mean you don't list the smaller and bigger modules in the list"
6. **Every module, nested or not, gets its interface and external integration tests designed and mocked up front.** User: "nested modules still get their interfaces and external integration tests designed/mocked up front."
7. **Lean on proven design; don't reinvent wheels** (see level 5 above).
8. **Encapsulate and organize complexity.** Each module hides its complexity behind a simple interface; callers never handle its internals. User: "we need a focus on complexity encapsulation"
9. **Never mix levels of detail.** Every function, and every module's public surface, works at one scope. A high-level function calls only things of similar scope, reading as a list of steps; string handling, raw conditionals and I/O live in the lower-level functions those steps call. The goal is organizing complexity, not reader comfort. User: "what is VERY IMPORTANT is not mixing levels of detail in code. for example a top level main() fucntion calls things. It should have similar SCOPE calls. it should NOT look like: loadStorageHandler(), showLogin(), if login = x then y, using \"string\".. plus ... then do this..." and "our goal isn't so much 'keep the humans from switching modes' as it is 'don't fill up the box of clipboards with loose sheets of paper' because we hve to manage the groups of paper...."

### Approaches for reference (to help, not to apply mechanically)

Use these wherever possible to keep code cohesive and to organize complexity effectively.

- **Cohesion types** (Constantine and Yourdon, *Structured Design*), strongest to weakest ([Wikipedia](https://en.wikipedia.org/wiki/Cohesion_(computer_science)), [history](https://arxiv.org/pdf/2507.09596)):
  1. Functional: every part contributes to one well-defined task.
  2. Sequential: one part's output is the next part's input.
  3. Communicational: the parts work on the same data.
  4. Procedural: the parts follow a set order of execution.
  5. Temporal: the parts run at the same time (e.g. "startup").
  6. Logical: the parts share only a category (e.g. "operations tooling"). Avoid.
  7. Coincidental: no meaningful relation (a "utils" grab-bag). Avoid.
- **Information hiding** (Parnas, 1972): split by design decisions likely to change; each module hides one, rather than following processing steps. ([paper](https://www.cse.sc.edu/~mgv/csce590f20/ParnasCriteria.pdf))
- **Single Responsibility and Common Closure** (Martin): "Gather together the things that change for the same reasons. Separate those things that change for different reasons." CCP applies it to packages. ([Clean Code blog](https://blog.cleancoder.com/uncle-bob/2014/05/08/SingleReponsibilityPrinciple.html), [CCP](https://oowisdom.csse.canterbury.ac.nz/index.php/Common_closure_principle))
- **Deep modules** (Ousterhout): a simple interface over substantial hidden work; beware shallow pass-through pieces ("classitis"). Use it to judge interfaces, not to argue against small modules. ([Stanford lecture](https://web.stanford.edu/~ouster/cgi-bin/cs190-spring16/lecture.php?topic=modularDesign), [review](https://blog.pragmaticengineer.com/a-philosophy-of-software-design-review/))
- **Composed Method / SLAP** (Beck; named the Single Level of Abstraction Principle by Ford; restated by Martin): keep all operations in a method at the same level of abstraction. ([c2 wiki](https://c2.com/ppr/wiki/WikiPagesAboutRefactoring/ComposedMethod.html), [O'Reilly](https://www.oreilly.com/library/view/the-productive-programmer/9780596519780/ch13.html), [DZone](https://dzone.com/articles/the-single-level-of-abstraction-principle))
- **Coupling** (Constantine): modules depend on each other as little and as plainly as possible. Sub-types not yet researched.

## Related decisions

- **Knowledge bases are not a level.** User: "the knowledgebases are, like in current agent planing tool, separate things that can be or not be exposed to a project (work order). kbs are not a level"
- **No separate requirement branches.** User: "sticking them into completely separeat branches is a failing proposition"
- **Requirements live on the node they govern.** (Corrected 2026-11-23, level 5: requirements do NOT pass down. User: "We don't pass requirements down to child nodes. What passes down is a generic context block; 'requirement' is a more specific thing.")
- **Honor system.** The agent does the research and includes links, with no file-and-line citation system. User: "the honor system means you trust the agent to do the research. yes include links"
- **Questions** go to a backlog and are asked in batches (user's answer to the clarifying questions).
- **Work on `main`**, with no branches until agents split off to work on separate modules.

- **All levels, every time.** No reduced level sets for small requests; simple standalone requests don't use the process. User: "honestly all levels aren't really bad even for a small request so the previous idea that we use different number of layers for smaller requests is wrong."
- **Broader than a workorder.** The README rule that a workorder never holds a whole project is old guidance. User: "this plan supports more broad plans/goals"
- **Escalations and tech spikes are sibling tasks** (2026-11-23, level 5; supersedes the "queue events" wording below where they differ). User: "They're all just work nodes. An escalation is a task: when a work task needs to escalate, it creates a task as its sibling, placed before it, so that flow moves to that new task first. This was already hammered out. A worker can raise a tech spike the exact same way: it's placed before the worker's task and runs, and when it's done, control flows back to the task that raised it. Escalations and tech spikes use the same mechanism, tied together in the same code."
- *(Earlier wording, kept for its resolution rules)* **Escalations are queue events.** They belong to the node that raised them, and the user is alerted. On review, the user decides whether the task or any layers above need adjusting, then work moves to the highest layer that needs it and back down. User: "escalations are events in a queue. they aren't part of a layer or task node apart from being related to the node that escalated it. if anything the escalation belongs to the node creating it, and user is alerted. when it gets reviewed, THEN it can be decided if the task or any layers above need to be adjusted, moving to the highest layer needing adjustment and working down to resolve."
  - **Resolving an escalation.** Once every issue is fixed, in the layers above and in the task node itself, the escalation on the work node is marked resolved with notes, and the task resumes with an instruction to review the escalation. A worker can never edit its task node directly; app permissions lock it. User: "when an escalation is resolved, meaning all issues above and including the task node details itself (which a worker cannot edit directly ever, locked by app permissions rigidly), the escalation attached to the work node is marked resolved with notes, and the task is resumed with instruction to review the escalation"
- **Level 3 is named "High-level plan"** (user's choice).
- **The Philosophy and Plan docs are updated to match** (user approved). Copies are in this folder.
