#!/usr/bin/env bash
# Run every project x condition x rep (3 reps) with 5 in parallel. TRIAL_SCRATCH must be set (temp copies live there).
E="$(cd "$(dirname "$0")" && pwd)"
rm -rf "$E/logs"
mkdir -p "$E/logs"
for rep in 1 2 3; do for c in A B C; do for p in shadow_secrets config_merge shared_state timezone_day vendored_api; do
  echo "$p $c $rep"
done; done; done | xargs -P 5 -L 1 python3 "$E/run_trial.py" > "$E/logs/_summary.jsonl"
