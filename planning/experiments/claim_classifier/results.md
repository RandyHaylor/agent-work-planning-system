# Claim-classifier reviewer experiment (2026-11-26)

Files: `cases.json` (32 hand-labelled cases: 10 good claims, 16 defective claims, 6 summary cases), `run_experiment.py` (prompts + runner), `analyze.py`, raw `results_gemma.jsonl` (1 run, temperature 0, one call at a time) and `results_haiku.jsonl` (3 runs per case, `claude -p --model haiku --tools ""`).

Defect = positive class (reviewer should fail it). The current prompt was not run on summary cases, because today nothing reviews summaries (gap 2).

| backend | prompt | n | TP | FN | false fail | TN | precision | recall | median latency s |
|---|---|---|---|---|---|---|---|---|---|
| gemma | current | 26 | 14 | 2 | 2 | 8 | 0.88 | 0.88 | 3.3 |
| gemma | classifier | 26 | 16 | 0 | 0 | 10 | 1.00 | 1.00 | 5.0 |
| gemma | summary_review | 6 | 3 | 0 | 0 | 3 | 1.00 | 1.00 | 2.2 |
| haiku | current | 78 | 41 | 7 | 0 | 30 | 1.00 | 0.85 | 7.9 |
| haiku | classifier | 78 | 48 | 0 | 1 | 29 | 0.98 | 1.00 | 8.3 |
| haiku | summary_review | 18 | 9 | 0 | 3* | 6 | 0.75 | 1.00 | 9.5 |

\* s02 is my labelling error: the summary says "rather than Redis", but the cited-content line I wrote leaves out "no redis". Haiku was right all 3 times. Gemma passed it. Corrected, Haiku summary precision is 1.00.

## Notable misses

- **Current prompt, Haiku:** it says the defect in its reason and still passes. Examples: d02 "PDF not in slice" passed 3 of 3 times. d11 "retry/backoff unsupported" passed 2 of 3. The "user states the requirement directly: PASS" rule overrides the "adds nothing" rule. It also passed a requirement tagged `note` (d12) once.
- **Current prompt, Gemma:** it passed a 3-sentence item backed by a single "yes" (d09). It passed a requirement that carried a technical claim cited only to the user (d16). It failed two true notes (g06, g07).
- **Classifier:** one false fail in 78 Haiku runs (g03: it didn't accept a "yes" to a proposal as support). Gemma got every case right.

## Classifier prompt

`CLASSIFIER_PROMPT` in `run_experiment.py`. Its steps:
1. Split the claim into sentences.
2. Label each sentence user_claim, technical_claim or none.
3. Give each claim sentence a supporting citation index or "unsupported". Origin rules: user claims need a user quote, technical claims need a document. A brief confirmation covers only what was proposed. Any added detail makes the sentence unsupported.
4. Check the tag: a note fails on any claim; requirement and decision need a user_claim; technical and documentation need a technical_claim.

It outputs strict JSON: `sentences[]`, `tag_ok`, `passed`, `reason`. The existing `parse_verdict` reads it unchanged, since only `passed` and `reason` are required. The summary prompt is `SUMMARY_PROMPT` in the same file.

## Recommendation

- Adopt option B (the classifier prompt) and option C (summary review). The classifier closed every miss of the current prompt on both backends and added no meaningful false fails.
- Use local Gemma as the default backend. It was perfect on this set, the fastest (about 5 s vs 8 s), and free. Keep Haiku as the second opinion (option E). Haiku's per-sentence reasons are good evidence for a reviewer.
- Caveats: the set is small and synthetic, and I wrote the cases. Run it against real review packets before relying on it. Keep `max_tokens` around 1200, because the per-sentence JSON is longer than today's 256.

## Sentence-by-sentence reviewer (2026-11-27, build log #55)

`run_sentence_review.py` runs the 31 claim cases through the real `SentenceBySentenceReview` on local gemma4 (`results_sentence_gemma.jsonl`). Defects caught 20/20. Good items passed 8/11: g06, g07, h06 failed. All three are uncited notes (a to-do, a work status, an open question with options). Gemma calls them unsupported claims. Arguably right under the 2026-11-27 goal of catching agent guesses (g07 reports work with no evidence; h06 offers options the agent made up). A rule saying "status/to-do/question makes no claim" did not change the result and was removed. About 3-6 s per review (3-5 turns).
