# Troubleshooting-protocol experiment (Haiku), 2026-11-26

Question: do troubleshooting-protocol rules reduce guess-and-try loops and first-idea latching in Haiku agents? Sources and proposals: `planning/DISCUSSION-2026-11-26.md` section 3.

## Setup

- 5 mini-projects in `projects/`. Each fails `./run.sh`, the obvious first guess is wrong, and a hidden probe in `checks.py` tests the root fix:
  - `shadow_secrets`: a local `secrets.py` shadows the stdlib.
  - `config_merge`: a shallow `dict.update` merge of the local config gives `KeyError: 'url'`.
  - `shared_state`: a class-level list is shared between instances, so a test fails depending on order.
  - `timezone_day`: local-time `fromtimestamp`; `run.sh` sets `TZ=Pacific/Auckland`.
  - `vendored_api`: the vendored tinycsv 2.0 changed the default for `header`.
- Conditions (`run_trial.py`), all run with `claude -p --model haiku` (claude-haiku-5-5), `--safe-mode`, `dontAsk`. Tools: Read/Edit/Write/Glob/Grep. Bash was allowed only for `./run.sh`, `ls` and `mv`. Prompt: "Make it pass. Do not edit run.sh or the test files."
  - A: system prompt "Fix the failing command."
  - B: A plus the protocol: a TROUBLESHOOTING.md record, the error verbatim, research of the error only with evidence listed, at least 3 ranked candidates checked cheapest first, one change at a time, and re-research after 2 identical failures.
  - C: B plus the `loopguard.py` wrapper. After 2 identical failures (signed by the last `*Error:` line) it prints STOP and refuses to run until the record is updated.
- 3 reps per cell, 45 runs. Scoring:
  - `checks.py`: root fixed, and symptom patch (the command passes but the probe fails, or a protected file was edited).
  - `trace.py`: edit->run cycles, edits, tokens and cost.
  - `judge.py` (a Sonnet judge): hypotheses stated before the first code edit, and whether the first edit targeted the wrong first guess.
- Raw logs are in `logs/`: stream-json transcripts, diffs, records, check and judge results. All rows are in `results.jsonl`.

## Results

| cond | root fixed | symptom patch | edit->run cycles | code edits | hypotheses before 1st edit | 1st hypothesis = root | 1st edit on wrong guess | STOPs | $/run | s/run | out tok |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A | 12/15 | 1/15 | 0.80 | 1.13 | 1.13 | 14/15 | 1/15 | 0 | 0.0022 | 9.3 | 1971 |
| B | 13/15 | 0/15 | 0.60 | 1.00 | 2.27 | 15/15 | 0/15 | 0 | 0.0054 | 24.0 | 5575 |
| C | 14/15 | 0/15 | 0.53 | 1.07 | 2.47 | 15/15 | 0/15 | 1 | 0.0059 | 26.7 | 6296 |

Results per project are printed by `python3 aggregate.py`. All misses are in `shadow_secrets` (A 0/3, B 1/3, C 2/3). The other four projects are 3/3 in every condition.

## What happened

- **A ceiling effect.** Haiku 5.5 named the root cause first in 44/45 runs and never entered a guess-and-try loop. The errors and the repo held enough evidence (traceback path, CHANGELOG, docstring "UTC") that reading the code was enough. These bugs did not trigger the failure mode we are trying to fix.
- **The `shadow_secrets` misses are mostly a harness artifact.** Haiku often tried to delete or rename the file with `rm`, or with commands chained after `cd ... &&`, and those were denied. It then stopped with the correct diagnosis but only half applied it. The one real symptom patch was A rep 1: it replaced `token_hex` with `os.urandom(16).hex()` and wrote that "the clean fix is to rename secrets.py". It knew the root cause and patched around it because that was easier.
- **The loop limiter fired once** (C rep 3, shadow_secrets). The partial rename failed twice with the same error, STOP was injected, the agent updated the record, finished the rename and passed. This is the only observed case of the intended recovery.
- **The protocol roughly doubled the number of hypotheses** (1.1 to 2.3-2.5), but the extra ones were mostly ruled out "by logic" after the answer was already known. It was ritual, not real differential diagnosis.
- **Cost:** the protocol took about 2.5x tokens and time (still under $0.01 per run).

## What helped most

1. Plain "read the error, then the code it points at" behaviour, which the base model already does on legible bugs.
2. "Fix the root cause, not the symptom" (B/C) removed the one symptom patch.
3. The hard limiter was cheap and did the right thing the one time it fired. These tasks were too easy to test it properly.

## Recommendations for our system

- **Prompt rules in presets:** keep these, but short: the error verbatim, the evidence read, root cause before the fix, no symptom patches. A full ranked-candidates ritual in every preset wastes tokens on easy bugs.
- **Loop limiter as a client hook:** worth building. It is cheap, it is invisible unless a loop happens, and it worked when triggered. Key it on the error signature, and unlock it with a record update (or a new research entry on the server).
- **Troubleshooting-record node + reviewer:** require it only after the limiter fires (or after the 2nd failed run). Then the reviewer checks it: at least 3 candidates, query terms taken only from the error, and the cheapest checks done first. That puts the cost where the failure mode actually occurs.
- **Next experiment needed:** these results do not show a reduction in looping, because none occurred. The next round needs harder bugs where the error misleads and the cause is not visible in the repo: two interacting causes, a misleading traceback, or a cause outside the named file. It should also use a fair tool set (allow `rm`, and allow `cd` chains inside the work dir). Long-context runs, where decay sets in, should be tested too.
