# Nothing-lost experiment results (2026-11-28)

Decision: build log #60 (2), "Add it (Recommended)": requirement and decision restatements must not drop or weaken any condition, limit, exception or hedge in the cited user quote or the approved proposal; "measure with dropped-condition cases first".

Cases: `cases.json`, 13 requirement/decision claims each citing one stored user exchange (agent question = PRE-INPUT CONTEXT, user answer = the cited line). 8 drop or weaken something (L1 "In-app only for now." -> "Notifications are in-app.", L2 drops an "unless" exception, L3 drops "never for payment calls", L4 drops "maybe ... if the hosting allows it", L5 drops a 7-day grace period, L6 weakens "at most 100 MB" to "a size limit", L7 drops "for the finance team only" from an approved proposal answered "yes", L8 drops "of inactivity"); 5 are faithful restatements (F1-F5). Written and labelled by the agent.

Runner: `run.py` runs the shipped review methods through the real `local_llm` backend (endpoint `local_gemma4`, the shared llama.cpp server), one call at a time. Rows: `results_gemma.jsonl` (`baseline` = reviewer before the check, `with_check` = after).

| reviewer | granularity | dropped conditions caught | faithful passed | s per review |
|---|---|---|---|---|
| before the check | per_sentence | 2/8 | 5/5 | 3.2 |
| before the check | bulk | 2/8 | 5/5 | 1.5 |
| with the check | per_sentence (one extra turn) | **8/8** | **5/5** | 4.6 |
| with the check | bulk (extra `dropped_conditions` field) | **8/8** | **5/5** | 2.9 |

- Before the check the sentence question only caught the two drops that make the sentence itself wrong (L4 "maybe" -> "uses", L8 "of inactivity"); the six others ("only for now", "unless legal asks", "never for payment calls", the grace period, the 100 MB number, "finance team only") passed.
- With the check every drop was named in the reason (e.g. "dropped 'only for now'", "for the finance team only: The claim omits the restricted audience specified in the proposal"), and no faithful restatement was failed.
- Cost: per_sentence +1 turn (~1.4 s); bulk ~+0.4 s on passes, more on fails (longer answer).

Caveats: small synthetic set written by the agent, one run, one model (gemma4). Haiku not run (no paid runs in this build).
