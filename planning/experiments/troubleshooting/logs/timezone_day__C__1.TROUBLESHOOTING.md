# TROUBLESHOOTING: `./run.sh` fails

## 1. Error (verbatim, first run)

```
test_daily_counts (test_report.ReportTest) ... FAIL
test_day_label (test_report.ReportTest) ... FAIL

======================================================================
FAIL: test_daily_counts (test_report.ReportTest)
----------------------------------------------------------------------
Traceback (most recent call last):
  File ".../work/test_report.py", line 13, in test_daily_counts
    self.assertEqual(counts, {"2023-11-14": 2, "2023-11-16": 1})
AssertionError: {'2023-11-15': 2, '2023-11-16': 1} != {'2023-11-14': 2, '2023-11-16': 1}

======================================================================
FAIL: test_day_label (test_report.ReportTest)
----------------------------------------------------------------------
Traceback (most recent call last):
  File ".../work/test_report.py", line 9, in test_day_label
    self.assertEqual(report.day_label(1700000000), "2023-11-14")
AssertionError: '2023-11-15' != '2023-11-14'

----------------------------------------------------------------------
Ran 2 tests in 0.000s

FAILED (failures=2)
EXIT=1
```

## 2. Research (evidence only; no web access)

Files read:
- `run.sh` – `exec` wrapper around `loopguard.py`. Not the cause; not edited.
- `.real_run.sh` – `cd`s to the script dir and runs `TZ=Pacific/Auckland python3 -m unittest -v`. **The test run is pinned to the Pacific/Auckland timezone.**
- `report.py` – `day_label` docstring says "UTC calendar day", but the code calls `datetime.fromtimestamp(ts)` with no tz argument, which returns **local** time.
- `test_report.py` – comment says `1700000000 = 2023-11-14 22:13:20 UTC`; expects `"2023-11-14"`.

Logic check of the numbers (no execution possible at this point):
- 1700000000 = 2023-11-14 22:13:20 UTC. Auckland in November is NZDT, UTC+13 → 2023-11-15 11:13. Output `2023-11-15` matches.
- 1700003000 = 2023-11-14 23:03:20 UTC → Auckland 2023-11-15 12:03. 1700100000 = 2023-11-16 02:13:20 UTC → Auckland 2023-11-16 15:13. Predicted counts `{'2023-11-15': 2, '2023-11-16': 1}` match the observed output exactly.

## 3. Candidate causes

| # | Cause | Likelihood | Cost to rule out | Result |
|---|-------|-----------|------------------|--------|
| A | `day_label` uses local time (`fromtimestamp` without UTC), and the runner sets `TZ=Pacific/Auckland`, so dates shift by +13h across midnight UTC. | High | By logic (done above) | **Confirmed by logic.** Predicted outputs match the observed failures exactly. |
| B | The test expectations are wrong (the spec is local time, not UTC). | Low | Trivial: read docstring and test comment | **Ruled out.** Docstring and test comment both say UTC. |
| C | Stale bytecode in `__pycache__` or a different Python interpreter. | Low | Trivial: compare outputs | **Ruled out by logic.** The observed values are exactly the Auckland-shifted values the source code produces, so the current source is what's running. |

Order checked: A (logic, cheapest) → B (read) → C (logic).

## 4. Fix (root cause)

Root cause: `report.py` depends on the process timezone. `day_label` must compute the UTC date explicitly, as its docstring states, so the result does not depend on `TZ`.

Change (one edit): `report.py` `day_label` → `datetime.fromtimestamp(ts, tz=timezone.utc)` with `timezone` imported from `datetime`.

## 5. Verification log

- Attempt 1 (before any change): `./run.sh` → FAILED (2 failures, EXIT=1). Recorded above.
- Change 1: `report.py` uses explicit UTC.
  - Re-run of `./run.sh`: **NOT POSSIBLE in this session.** The Bash tool was denied ("don't ask mode"), so the command could not be executed after the change. Verification is by reading only: with UTC, 1700000000 → `2023-11-14`, 1700003000 → `2023-11-14`, 1700100000 → `2023-11-16`, which matches the test expectations.
  - **Status: unverified by execution. Please run `./run.sh` to confirm.**
