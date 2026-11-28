# Node-validation experiment results (2026-11-27)

Plan: `PLAN.md`. Test set: `nodes.json`, 12 whole nodes (definition of done, design, plan, work report, research; 2 clean controls), 61 sentences: 23 seeded guesses, 33 backed, 5 neutral (to-do, status, question). I wrote and labelled them. Runner `run.py`, scorer `analyze.py`, raw rows `results_gemma.jsonl` and `results_haiku.jsonl`. A sentence counts as flagged if the variation marks it as unsupported or guessed.

| backend | variation | guesses caught | backed flagged | neutral flagged | calls/node | s/node |
|---|---|---|---|---|---|---|
| gemma | V1 sentence review (shipped reviewer turns) | 23/23 | 5 | 3 | 6 | 7.7 |
| gemma | V2 atomic claims | 20/23 | 2 | 1 | 7 | 14.3 |
| gemma | V3 facts + requirements lists | 22/23 | 3 | 3 | 5 | 7.0 |
| gemma | V4 one "list every guess" question | 22/23 | 1 | 1 | 1 | 2.1 |
| haiku | V1 | 23/23 | 8 | 2 | 6 | 9.3 |
| haiku | V4 | 23/23 | 5 | 1 | 1 | 2.6 |

The first Haiku run failed in the harness: `claude -p --output-format json` returned an event list. The parser was fixed and the run repeated; the analyzer uses the last row per node.

## What the flags on "backed" sentences are

Most are small agent decisions that I labelled as backed because a reference nearly covers them. Each one has a document for the "how" but no user approval for the choice:
- "so the app only reads its config"
- "a form with display name and email"
- "errors next to the fields"
- "store the token with keyring"

Under the 2026-11-27 goal (every plan point, stack choice and design needs approval or proof), these flags are right. The truly wrong flags are:
- to-do and question lines (V1 on both models)
- "Step 1: an install section" (Haiku V1: it wanted proof that install comes first)
- "The job queue lives in a Postgres table" (Haiku V1: "table" vs "in Postgres")

Haiku V1 also caught a dropped qualifier. The reference says Secret Service is the "default" backend; the node dropped "default". That is the "nothing lost" check in action.

## Misses

Only on Gemma: "Users are locked out after five failed attempts", where the code is `attempts > 5`, so the lockout comes on the sixth (V2, V3, V4). V2 also missed "We should use pdfminer.six" and "The user wants a logout command".

## Findings

1. A per-node V4 screen (one call) catches as much as per-sentence V1 on Haiku, and nearly as much on Gemma, at a quarter of the time.
2. Free text with citations does as well as the V3 lists. The V3 lists were laid out mechanically from my labels; real agents writing their own lists were not tested.
3. Atomic-claim decomposition (V2) was the slowest and missed the most on Gemma.
4. Both models flag unapproved design choices once asked about the whole node. Requiring a "why" (a user requirement or approval) for each design or plan point would make that a rule, not luck.

## Caveats

Small synthetic set written by the agent; one run per model; whole-node prompts only had the node's own references.
