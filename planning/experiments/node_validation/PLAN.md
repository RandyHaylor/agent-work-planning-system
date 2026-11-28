# Experiment plan: validating whole nodes (DRAFT, not approved)

User, 2026-11-27: "build and test some other variations of how we can check node content. This means the design nodes and all nodes. We need ultimately to be able to catch any work, dod, plan, fact claim, design suggestion, etc that seems like only the agents guess. It's still uncertain how we'll accomplish this. It's possible that each node will need a "facts" list with claims and proofs for each, and a user requirements list with user quotes supporting all requirements. Let's try to figure out a working algorithm and system to achieve quantifying and validating"

## Goal

For a whole node (title, context summary, every content item), find every statement the agent could only have guessed, and put a number on it: how many statements, how many backed, which ones aren't.

## Known approach to build on

Decompose-then-verify: split text into atomic claims, check each against sources. FActScore (Min et al. 2023, https://arxiv.org/abs/2305.14251) scores the fraction of atomic facts supported. SAFE (Wei et al. 2024, https://arxiv.org/abs/2403.18802) does the same with search. Our sources are the node's cited references, not the web.

## Test set

About 12 realistic nodes, one or two per level and kind: definition of done, design (module choice), plan, task work report, research summary, plus clean controls. Each has a known set of seeded guesses (made-up numbers, invented user requirements, unbacked design choices, "tests pass" with no output, an option list the user never offered), and a known set of backed statements. I write and label them, so the same caveat as before applies: run on real nodes afterwards.

## Variations

| # | Name | How | What the agent writes |
|---|---|---|---|
| V1 | Sentence review, whole node | Today's reviewer applied to every sentence of title, summary and all content items together, with all the node's references | Free text (as now) |
| V2 | Atomic claims | Model splits the node into atomic claims (FActScore step 1); each is asked "supported by an included reference?" one by one in the same session | Free text |
| V3 | Facts + requirements lists | Node carries `facts: [{claim, citation}]` and `requirements: [{requirement, user quote citation}]`; code checks every list item has a citation; reviewer checks each item against its citation; then each sentence of the free text is asked "is this covered by a listed fact or requirement?" | Structured lists + free text |
| V4 | Guess hunt | One adversarial question per node: "list every statement the writer would have had to guess" | Free text |

Score per variation: seeded guesses caught (recall), backed statements wrongly flagged, model calls and seconds per node. Backends: local gemma4 for all; Haiku for the best two.

## Output

`results.md` with the table and recommendation. No change to the system until you pick.
