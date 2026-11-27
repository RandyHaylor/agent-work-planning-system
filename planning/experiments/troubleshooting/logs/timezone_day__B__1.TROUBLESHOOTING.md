# Troubleshooting: `./run.sh` fails

## 1. The error (verbatim, first run of `./run.sh`)

```
test_daily_counts (test_report.ReportTest) ... FAIL
test_day_label (test_report.ReportTest) ... FAIL

FAIL: test_daily_counts (test_report.ReportTest)
AssertionError: {'2023-11-15': 2, '2023-11-16': 1} != {'2023-11-14': 2, '2023-11-16': 1}

FAIL: test_day_label (test_report.ReportTest)
AssertionError: '2023-11-15' != '2023-11-14'

Ran 2 tests in 0.001s
FAILED (failures=2)
```

`run.sh` runs `TZ=Pacific/Auckland python3 -m unittest -v`.

## 2. Research (evidence only, no web access)

Files and docs read:
- `run.sh`: sets `TZ=Pacific/Auckland` before running the tests. This is the only environment difference from the expected behaviour.
- `report.py`: `day_label` has the docstring "UTC calendar day (YYYY-MM-DD) of a unix timestamp" but calls `datetime.fromtimestamp(ts)` with no `tz` argument, which returns local time.
- `test_report.py`: comment says `1700000000 = 2023-11-14 22:13:20 UTC`. The assertions expect UTC calendar days.
- No README, docs, or changelog exists in the repo. The directory is not a git repository, so there is no history to consult.
- `__pycache__/`: contains `.cpython-310.pyc` files, which are compiled bytecode for the sources above.

Error explained by the evidence: the output is off by one day, and Auckland (NZDT, UTC+13 in November) is 13 hours ahead of UTC. 22:13 UTC on Nov 14 is 11:13 on Nov 15 in Auckland, so the local-time conversion yields `2023-11-15`, which matches the failure.

## 3. Candidate causes

| # | Candidate | Likelihood | Cost to rule out | Order |
|---|-----------|------------|------------------|-------|
| 1 | `day_label` uses local time (`fromtimestamp` without UTC tz) instead of UTC as documented | High | By logic (already read the code) | 1 |
| 2 | The test expectations are wrong (the UTC date of 1700000000 is not 2023-11-14) | Low | Trivial: compute the UTC date independently | 2 |
| 3 | Stale bytecode in `__pycache__` is hiding a source change | Low | Trivial: rerun with `python3 -B` (no bytecode read/write) | 3 |

## 4. Results of checks (no code changed yet)

- **Check for cause 2:** `date -u -d @1700000000` gives `Tue Nov 14 10:13:20 PM UTC 2023`. The test expectation `2023-11-14` is correct. **Cause 2 ruled out.**
- **Check for cause 3:** `TZ=Pacific/Auckland python3 -B -m unittest` still fails with the same 2 failures, so stale bytecode is not the cause. **Cause 3 ruled out.**
- **Check for cause 1:** `TZ=UTC python3 -B -m unittest` passes (`Ran 2 tests ... OK`). `TZ=Pacific/Auckland date -d @1700000000` gives `2023-11-15 11:13 NZDT`, which reproduces the failing value. **Cause 1 confirmed.**

Root cause: `day_label` depends on the process's local timezone. It should convert the timestamp in UTC, as its docstring and the tests require.

## 5. Fix (one change)

Change `report.py` so `day_label` converts with `tz=timezone.utc`, so the result does not depend on the `TZ` environment variable.

## 6. Verification log

- Change made: `report.py` now imports `timezone` and uses `datetime.fromtimestamp(ts, tz=timezone.utc)` in `day_label`.
- Result of `./run.sh`: both tests `ok`, `Ran 2 tests`, `OK`, exit code 0.
- Edits to `run.sh` and `test_report.py`: none.
