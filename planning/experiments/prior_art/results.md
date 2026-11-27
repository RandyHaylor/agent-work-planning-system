# Prior-art experiment: results (2026-11-26)

Question: does a required, cited prior-art step stop Haiku planners reinventing wheels?

Setup: `run.py` (conditions + D checker), `score.py` (code checks + Haiku judge), `raw/*.json` (prompts, outputs, checks).
10 tasks (8 with a standard library, 2 in-house: `novel_heat` formula, `novel_qrx` binary format) x 4 conditions x **1 rep** = 40 calls, `claude -p --model haiku`, isolated via `../common.py` (`--safe-mode`, neutral cwd, prompt on stdin).
Package existence: PyPI/npm JSON API. URLs: HEAD/GET, 403/429 counted as alive.

Caveat: a first run (2 reps) was discarded. It ran inside the repo without isolation (the project CLAUDE.md "don't reinvent wheels" could reach the baseline), and C/D failed because `--allowed-tools` swallowed the prompt. n=1 per cell, so treat the differences as indicative only.

## Results

| Cond | Reused existing (8 std tasks) | Pkgs cited | Non-existent pkgs | URLs cited | Dead URLs | Novel: explicit "none found" | Novel: invented lib | Avg words | Avg out tokens | Avg $ |
|---|---|---|---|---|---|---|---|---|---|---|
| A baseline | 7/8 | 8 | 0 | 0 | 0 | 0/2 | 0/2 | 234 | 848 | 0.001 |
| B prompt rule | 8/8 | 39 | 0 | 0 | 0 | 0/2 | 0/2 | 228 | 2030 | 0.001 |
| C MADR + web | 8/8 | 28 | 0 | 35 | 0 | 0/2 (judge); 1/2 by reading | 0/2 | 309 | 3326 | 0.043 |
| D C + checker | 8/8 | 30 | 0 | 42 | 0 | 1/2 | 0/2 | 322 | 3736 | 0.048 |

The D checker found nothing to fix (0 revisions in 10 runs).

## Examples

- The only baseline miss: `A_iso_duration` planned a hand-written regex parser ("stdlib only") instead of `isodate`/`aniso8601`. B, C and D all chose a library.
- Baseline already reuses on the obvious tasks: bottleneck, ajv, python-dotenv, tenacity, APScheduler, difflib.
- Novel tasks, all conditions: correct stdlib/custom build, no invented library. C/D wrote the best records. `C_novel_heat` listed its queries and registries, said "Composite aging-priority formula: NONE FOUND", and rejected real MCDM libraries (pymcdm, scikit-criteria) with quoted reasons. `C_novel_qrx` compared stdlib struct, construct and NumPy, each with a real URL. The judge missed the NONE FOUND in C_novel_heat, so judge scores on "none found" are noisy.

## Findings

- Invented-package rate: **0/105** cited packages across all conditions, and 0/77 dead URLs. On these well-known tasks Haiku did not show the ~20% hallucination rate from arXiv 2406.10279. These tasks are easy; obscure domains are where invention happens.
- The cheap prompt rule (B) closed the only reuse gap. It cost no more dollars, but output tokens rose 2.4x.
- C/D (MADR + web) added real, checkable citations and honest search records for novel work, at about 40x the cost per call. The D checker was a no-op here, but it is cheap code (about 1 s per check) and is the only layer that would catch an invented package.

## Recommendation for our system

1. Add the **B rule to every planner/dev-manager/worker preset**. It gives the most per dollar.
2. Add a **`prior_art` claim tag** for any spec item introducing a component: >= 2 options including "existing library", each with a URL, a chosen option with a quoted reason, or a "none found" record with queries and registries.
3. Run the **registry/URL check in code** on every `prior_art` claim (always, not as a sampled review). It is cheap, it is deterministic, and it is the backstop for hallucinations this sample didn't trigger.
4. A **reviewer** judges build-vs-reuse quality and checks that "none found" lists real queries. Use web-research (C-style) only for items the reviewer flags or that are new to the project, because of the cost.
5. Follow-up: rerun with 3+ reps on harder or obscure tasks, where invention is more likely.
