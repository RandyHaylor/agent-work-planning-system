# Discussion: enforcement and agent failure modes (2026-11-26)

FOR DISCUSSION. Nothing here is decided. Options to choose from, with sources.


## 1. Enforced citations today

### What code enforces (server gate, deterministic)

- Every content write carries one claim tag
  - `requirement`, `decision`: need a user quote (user_exchange / proposal_response)
  - `technical`, `documentation`: need a loaded document or knowledge base reference
  - `plan`: any evidence
  - `note`: no citation
- Every citation exists, is not superseded, has a valid line range, and is an allowed origin
- Titles: not empty, at most 50 chars, no citation, not ending like a sentence
- A node can't be set done while any of its reviews are pending or failed

### What review checks (model, per content item)

- Does the cited slice support the claim; does the claim add anything the quote doesn't say
- Brief confirmations ("yes", "A") pass when the agent's question is in the pre-text
- A `note` fails if it actually makes a requirement or technical claim
- Title shape suggestions (not failures)

### Gaps that weaken "you can't make claims without the formal actual code"

1. **The agent picks the tag.** A requirement tagged `note` passes the gate; only the reviewer can catch it.
2. **Node title and context summary are never cited or reviewed** beyond the title shape rules. The summary is the text that passes down to every node below, so an uncited claim there spreads.
3. **One review per content item.** A multi-sentence item with one citation can carry extra uncited claims; the reviewer judges the whole item.
4. **Nothing requires coverage.** A level 2 (definition of done) node with no requirement content passes. Research quotes are required only if the agent chooses a technical tag.
5. **A pass is one model's opinion.** No second reviewer, no sampling for you to spot-check, no record of which model judged.
6. **Research quality isn't checked.** A citation proves the source says it, not that the right sources were looked for (see section 3).


### Options to close them (pick any)

| Option | Mechanism | Enforced by |
|---|---|---|
| A. Sentence-level citations | Every sentence in a requirement / decision / technical / documentation item must end with a citation | Code (sentence split + citation check) |
| B. Claim classifier | Reviewer first classifies each sentence (user claim / technical claim / none), then fails mismatched tags or uncited claim sentences | Review |
| C. Review summaries and titles | A node's context summary is reviewed against its own cited content and its ancestors' summaries | Review (code: summary changes open a review) |
| D. Level coverage rules | e.g. levels 1-2 need >= 1 cited requirement; level 3+ technical choices need a cited reference; module specs need a prior-art item (section 3) | Code |
| E. Second opinion and sampling | Failed or low-confidence verdicts re-reviewed by a second backend; a random sample queued for you | Code + review |
| F. Record the reviewer | Store backend + model + prompt version on each verdict | Code |

My recommendation: A + B + C + D first (they close gaps 1-4), F as a cheap add, E later.


## 2. Generic model calls (done) and pi (parked)

- pi CAN do a no-tools, no-session one-off (`pi --mode rpc --no-session --no-tools`; our parked backend used exactly that)
- Before today: the llama.cpp call sat behind the reviewer-backend strategy, but was a reviewer-only class with the URL and model hard-coded as defaults
- Now: `planning_system/model_calls/` is a generic one-off interface with an OpenAI-compatible implementation and named endpoints in `config/model_endpoints.json` (`local_gemma4`). The reviewer uses it. pi is parked.


## 3. Agent failure modes: research and proposals

### Sources (from two research agents; [U] = not verified at the source)

- Anchoring / premature closure and countermeasures (force alternatives, differential, "what else could it be?", checklists): [Croskerry 2003](https://www.kellogg.northwestern.edu/faculty/uzzi/ftp/restricted/articles/Cognitive%20Errors%20in%20Diagnosis%20-%20Academic%20Medicine%20-%202003.pdf), [Cognitive debiasing, BMJ Qual Saf 2013](https://psnet.ahrq.gov/issue/cognitive-debiasing-part-1-and-part-2), [AHRQ case](https://psnet.ahrq.gov/web-mm/possible-probable-sure-wrong-premature-closure-and-anchoring-complicated-case). Evidence that debiasing works is still thin.
- Scientific debugging (observe, hypothesize, predict, test, log each hypothesis): [Zeller, Why Programs Fail ch. 6](https://courses.cs.duke.edu/compsci308/spring26/readings/Zeller_Scientific_Debugging.pdf)
- Agans' 9 rules ("Quit thinking and look", "Change one thing at a time", "Keep an audit trail") [U]: [debuggingrules.com](https://debuggingrules.com/)
- LLM debugging effectiveness decays 60-80% within 2-3 attempts: [arXiv 2506.18403](https://arxiv.org/html/2506.18403v2); failed agent runs loop non-adaptively: [arXiv 2506.18824](https://arxiv.org/html/2506.18824v1); without debugging memory agents repeat mistakes: [arXiv 2508.12555](https://arxiv.org/pdf/2508.12555); fixes submitted without the output changing: [MIRAGE-Bench](https://arxiv.org/pdf/2507.21017)
- Your "research only the error" rule: biased query wording returns biased results: [arXiv 2311.09969](https://arxiv.org/pdf/2311.09969), [GU thesis](https://gupea.ub.gu.se/items/4f5df518-0b7d-43e0-9384-1e340707761e)
- Existing prompt-only skill: obra/superpowers "systematic-debugging" ("NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST"): [listing](https://claudemarketplaces.com/skills/obra/superpowers/systematic-debugging)
- Prior art: Rust RFC "Rationale and alternatives" + "Prior art" ("could this be done in a library?"): [template](https://raw.githubusercontent.com/rust-lang/rfcs/master/0000-template.md); MADR "Considered Options": [adr.github.io/madr](https://adr.github.io/madr/); design docs "Alternatives considered" incl. existing systems: [Industrial Empathy](https://www.industrialempathy.com/posts/design-docs-at-google/); "Choose Boring Technology" innovation tokens [U, secondary]: [glyph](https://blog.glyph.im/2024/07/against-innovation-tokens.html)
- No study found that LLMs over-build custom code (one found they over-use popular libraries: [arXiv 2503.17181](https://arxiv.org/html/2503.17181v2)); LLMs DO invent packages (19.7% of suggestions): [arXiv 2406.10279](https://arxiv.org/html/2406.10279v3) — so a reviewer must check cited libraries exist
- Docs lookup: Context7 MCP: [github.com/upstash/context7](https://github.com/upstash/context7)


### How each failure mode could fit our system

Our premise is: claims need formal cited evidence, enforced by code and checked by review. Each mode becomes a claim type that needs its own evidence.

**Reinventing wheels -> a required, cited prior-art claim**
- New claim tag `prior_art` on any plan / spec item that introduces a component, algorithm or pattern: must cite researched references (library, pattern, example) OR a cited "none found" search record (queries + registries searched)
- Options-considered structure (MADR): >= 2 options, always including "use an existing library/system"; each with a quoted reason
- Reviewer: checks cited libraries exist (registry lookup by code), license / maintenance noted, and rejects a custom build when a cited option meets the need without a quoted reason
- Optional: an innovation budget (each custom/novel choice needs your explicit approval node)
- Enforcement: code (tag + coverage rule D), review (quality), prompt (rule in all presets)

**Latching onto the first idea -> a differential, ranked by likelihood and cost to rule out**
- A troubleshooting record (an ordinary node with tagged content, not a new type): the error verbatim; >= N candidate causes; each ranked by likelihood and by cost to eliminate ("by logic" / "trivial check" / "costly"); cheapest eliminations first; results of each check
- Reviewer: fails a record with one candidate, or that skips a trivial check, or tests a costly one first without reason
- Enforcement: code (record required before a fix on a failing task; fields required), review, prompt

**Guess-and-try loop -> research the error only, then a loop detector**
- Research entries in the record must cite sources found by queries built from the error / stack trace / docs tokens only; queries are stored, and a check flags query terms that appear in neither the error nor the code (your "false premise self-fulfilling prophecy" rule)
- Loop detector: a client hook counts edit -> run -> same failure per error signature; after 2 cycles (the decay result) it blocks further edits until a new research entry or record exists
- Fix acceptance needs before/after evidence (the output actually changed) and the rejected-hypothesis log carried into context on retry
- Enforcement: code (hook + server state + query check), review, prompt


### Prompt rules alone are the weakest layer

The prompt builder (now our role prompt manager) should carry all three rules in the planner, dev-manager and worker presets. But every source and our own experience say rules alone don't hold, so the code + review layers above are the backstop.


## 4. tmux test (done)

- A fork ran a Haiku planner in tmux with our hooks in an isolated settings file; I acted as the user
- Passed: hook captured my answer, cite-exchange synced it, cited requirement accepted, uncited rejected, local gemma4 review passed
- Found and fixed: planners couldn't read a freshly synced user quote to cite it; the 422 hint named a command that doesn't exist
- Note: accepting folder trust added `/tmp/planning-tmux-test/scratch` to `~/.claude.json`
