# Supersede experiment results (2026-11-27)

Spec: `planning/05-spec-reference-supersede.md` (DRAFT). Cases: `cases.json` (8 cited user quotes, 15 new statements, 8 new-document-copy cases; written and labelled by the agent). Runner `run.py`, scorer `analyze.py`, rows `results_gemma.jsonl`, `results_haiku.jsonl`. Gemma and Haiku ran in parallel.

## A. Does a new user statement change an earlier cited quote?

| backend | variation | changes caught | false alarms (of pairs) | calls per statement | s per statement |
|---|---|---|---|---|---|
| gemma | Q1 one session, a turn per quote | 11/11 | 0/109 | 9 | 12.3 |
| gemma | Q2 one call, all quotes | 11/11 | 0/109 | 1 | 1.5 |
| gemma | Q3 isolated call per quote | 11/11 | 2/109 | 8 | 9.3 |
| haiku | Q1 | 10/10 (1 error) | 0/102 | 9 | 15.0 |
| haiku | Q2 | 11/11 | 0/109 | 1 | 2.0 |

- Both models were perfect with one call that lists every quote (Q2), 6-8x cheaper than per-quote turns.
- Q3 without a session gave 2 false alarms ("SQLite instead" flagged as changing backups and exports).
- Haiku Q1 once answered with text shaped like a tool call instead of JSON (S04): an unparseable answer, retried in production.
- Scale caveat: Q2 puts every cited quote into one prompt. A project with hundreds of quotes would need batches; untested.

## B. Trial review: does a claim still hold in the new copy of a document?

| backend | variation | holds judged right | broken page judged right |
|---|---|---|---|
| gemma | P1 diff-matched lines only | 6/8 | 8/8 |
| gemma | P2 whole new copy | 7/8 | 8/8 |
| gemma | P3 both | 7/8 | 8/8 |
| haiku | P1 | 5/8 | 8/8 |
| haiku | P2 | 7/8 | 8/8 |
| haiku | P3 | 7/8 | 8/8 |

- Matched lines alone (P1) fail when information moves elsewhere (B07): the diff points at the wrong lines.
- Gemma missed the added deprecation note in every variation (B08: "the exact text is still there"). Haiku caught it with the whole copy.
- Haiku failed "retried up to two times" vs "retries twice" (B06) in all variations: arguably right ("up to" allows fewer).
- Every error page and placeholder page was spotted by both models in every variation.

## Recommendation for the spec

- All-quotes check: one call per new statement listing every cited quote (Q2), batched for large projects; local gemma default.
- Trial review: give the reviewer the diff-matched lines AND the whole new copy (P3); add to the prompt that a deprecation or warning about the claimed thing counts as no longer supported; Haiku as second opinion when gemma says "holds".
