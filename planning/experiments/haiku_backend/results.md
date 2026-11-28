# Haiku through the real claude_code backend (2026-11-28)

Paid run approved by the user ("Yes do the paid calls"). `run.py` sends every case through `ReviewerBackendFactory().create("claude_code", "haiku", granularity)`: a persistent headless `claude -p --model haiku` session per worker thread, no tools, both granularities, with the nothing-lost check active for requirement/decision claims. Cases are agent-written: `claim_classifier/cases.json` (31) and `nothing_lost/cases.json` (13). Rows: `results.jsonl`; scorer: `analyze.py`.

| set | granularity | defects caught | good items failed | errors | median s |
|---|---|---|---|---|---|
| claims | bulk | 20/20 | 4/11 | 0 | 2.7 |
| claims | per_sentence | 20/20 | 3/11 | 0 | 10.6 |
| nothing_lost | bulk | 8/8 | 2/5 | 0 | 2.8 |
| nothing_lost | per_sentence | 8/8 | 1/5 | 0 | 14.5 |

Live: `scripts/live_review_run.py` passed end to end including its Haiku (claude_code) step, 6.7 s.

## The "good items failed"

- g06, g07: uncited notes; failing them is the accepted behaviour (build log #60 (4)).
- g03: the user approved "local gemma by default, Haiku as fallback"; the claim omits the fallback. Haiku is right; the case label was too lenient.
- F1 (nothing_lost): the quote covers finished-export notifications; the claim says all notifications. Haiku is right.
- g10 (bulk): "this agent's questions" generalised to all agents. Arguably right.
- F2 (bulk): "are kept" judged stronger than "keep". A nitpick.

So against corrected labels, Haiku's real errors are about 1 per 44 reviews. Bulk is about 4x faster than per-sentence on Haiku with the same catch rate, which supports the profile default (bulk for Haiku).
