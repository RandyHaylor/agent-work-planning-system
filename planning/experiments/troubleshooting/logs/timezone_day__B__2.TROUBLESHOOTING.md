# Troubleshooting: `./run.sh` fails

## 1. Error (verbatim, first run of `./run.sh`)

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
- {'2023-11-15': 2, '2023-11-16': 1}
?            ^

+ {'2023-11-14': 2, '2023-11-16': 1}
?            ^


======================================================================
FAIL: test_day_label (test_report.ReportTest)
----------------------------------------------------------------------
Traceback (most recent call last):
  File ".../work/test_report.py", line 9, in test_day_label
    self.assertEqual(report.day_label(1700000000), "2023-11-14")
AssertionError: '2023-11-15' != '2023-11-14'
- 2023-11-15
?          ^
+ 2023-11-14
?          ^


----------------------------------------------------------------------
Ran 2 tests in 0.000s

FAILED (failures=2)
```

Exit code: 1

## 2. Research (evidence only; no web access)

Files read:
- `run.sh`: runs `TZ=Pacific/Auckland python3 -m unittest -v`. It sets the process timezone to Auckland.
- `report.py`: `day_label` calls `datetime.fromtimestamp(ts)` with no `tz` argument. The docstring says "UTC calendar day (YYYY-MM-DD)". Python's `fromtimestamp` without `tz` returns local time, so the code disagrees with its own docstring.
- `test_report.py`: the comment says `1700000000 = 2023-11-14 22:13:20 UTC`, and both tests expect UTC dates.
- Repo docs and changelogs: none exist in this directory. The directory is not a git repository, so there is no history to check.

Observed from the error: `day_label(1700000000)` returned `2023-11-15`. That is the Auckland local date (NZDT, UTC+13), so the failure is the local-time conversion applied to a timestamp that should be read as UTC.

## 3. Candidate causes

| # | Candidate | Likelihood | Cost to rule out | Order |
|---|-----------|------------|------------------|-------|
| A | `report.py` uses naive `datetime.fromtimestamp`, which converts to the process's local timezone. `run.sh` sets `TZ=Pacific/Auckland`, so the dates shift. | High | Logic (read code + docstring) and trivial (run tests under different TZ values) | 1st |
| B | The test expectations are wrong (the timestamps really map to 2023-11-15 in UTC). | Low | Trivial: convert 1700000000 with explicit UTC | 2nd |
| C | The system lacks timezone data for `Pacific/Auckland`, so the TZ setting is ignored or misapplied. | Low | Trivial: `date` with `TZ=Pacific/Auckland` | 3rd |
| D | Python version difference changes `datetime` / `TZ` handling. | Low | Trivial: `python3 --version` | 4th |

## 4. Check results

- **Check A (TZ=UTC run):** `TZ=UTC python3 -m unittest` → `Ran 2 tests ... OK`. Under UTC, both tests pass, so the code and tests agree when local time is UTC.
- **Check B (TZ=Pacific/Auckland run):** same as run.sh → `FAILED (failures=2)`. The failure follows the TZ value.
- **Check C (explicit conversion of 1700000000):**
  - naive local under Auckland: `2023-11-15 11:13:20` (this is the wrong one for the tests)
  - `tz=timezone.utc`: `2023-11-14 22:13:20+00:00` (matches the test comment)
  - Candidate B is ruled out: the test's expected dates are correct UTC dates.
- **Check D (Python version):** Python 3.10.12. Not the cause of a version-specific bug; the behavior is the local-time conversion itself.
- **Check E (tz data):** `TZ=Pacific/Auckland date -d @1700000000` → `Wed Nov 15 11:13:20 AM NZDT 2023`. The tz data is present, so candidate C is ruled out.

Conclusion: candidate A is the root cause. Candidates B, C, and D are ruled out.

## 5. Fix (root cause)

Change `report.py` so `day_label` converts the timestamp to UTC explicitly, instead of depending on the process timezone. This matches the function's docstring. `run.sh` and the test files are not changed.

Change 1 (to be recorded after running): `datetime.fromtimestamp(ts)` → `datetime.fromtimestamp(ts, tz=timezone.utc)`, with `timezone` imported from `datetime`.

## 6. Change log

### Change 1: `report.py`
- Before: `from datetime import datetime`; `datetime.fromtimestamp(ts)`
- After: `from datetime import datetime, timezone`; `datetime.fromtimestamp(ts, tz=timezone.utc)`
- Command: `./run.sh`
- Result: `test_daily_counts ... ok`, `test_day_label ... ok`, `Ran 2 tests`, `OK`, exit code 0.
- Failure count went from 2 to 0. The same command had failed twice before this change, and this was the only code change made, so no re-research was needed.

## 7. Final status

`./run.sh` exits 0 with both tests passing. Only `report.py` was edited. `run.sh`, `test_report.py`, and the other test files are unchanged.
