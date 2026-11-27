# TROUBLESHOOTING: ./run.sh failing

## 1. Error (verbatim, first run of ./run.sh)

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

## 2. Research (read-only, error-specific)

Files and docs examined:
- `run.sh` — `exec python3 .../guard/loopguard.py ...`. Wrapper only; not the cause. Not edited.
- `.real_run.sh` — runs `TZ=Pacific/Auckland python3 -m unittest -v`. **This sets the process timezone to Pacific/Auckland (UTC+13 in November, NZDT).**
- `report.py` — `day_label` docstring says "UTC calendar day (YYYY-MM-DD) of a unix timestamp", but the body is `datetime.fromtimestamp(ts).strftime(...)`. `fromtimestamp` with no `tz` argument returns **local time**.
- `test_report.py` — comment says `1700000000 = 2023-11-14 22:13:20 UTC`. Expected labels are UTC dates.

Reading the error against the code: 1700000000 is 2023-11-14 22:13:20 UTC. In Auckland (+13) that is 2023-11-15 11:13:20 local. The code returned `2023-11-15`, which is the local date. The expected `2023-11-14` is the UTC date. Same pattern for `daily_counts`: 1700003000 (UTC 2023-11-14 23:03:20) becomes 2023-11-15 local, so both fall on 11-15 locally, giving `{'2023-11-15': 2, ...}`.

## 3. Candidate causes

| # | Cause | Likelihood | Cost to rule out |
|---|-------|-----------|------------------|
| A | `day_label` uses local time (`fromtimestamp` without `tz=`) while the spec is UTC, and the wrapper sets `TZ=Pacific/Auckland`, so the local date differs from the UTC date. | High | Logic (read code + docstring vs. error arithmetic) — done. Trivial run check: `TZ=Pacific/Auckland python3 -c "import report; print(report.day_label(1700000000))"` should print `2023-11-15`. |
| B | The test expectations are wrong (timestamps or dates don't match UTC). | Low | Logic — done: the test comment's own UTC conversion of 1700000000 is 2023-11-14 22:13:20, consistent with the expected label. Trivial check: `python3 -c "import time; print(time.strftime('%Y-%m-%d', time.gmtime(1700000000)))"`. |
| C | Stale bytecode in `__pycache__` or the TZ env var is not reaching Python. | Low | Trivial: run with `-B`; confirm `TZ` takes effect. Logic: `__pycache__` holds only compiled code, which doesn't change behavior when source is unchanged. |

Order of elimination: A (logic, done) → B (logic, done) → C (trivial).

## 4. Check results

- **Check A (logic):** Confirmed. Error values match local (Auckland) date arithmetic exactly. Consistent with the docstring/code mismatch.
- **Check B (logic):** Test expectations match the UTC dates in the test's own comment. Tests are correct and must not change.
- **Check C:** Not run. The Bash tool was denied in don't-ask mode, so no shell commands (including the trivial checks above and `./run.sh`) could execute in this session.

## 5. Root cause and fix

Root cause: `report.day_label` converts timestamps using the process's local timezone instead of UTC, as its docstring specifies. The wrapper's `TZ=Pacific/Auckland` exposes this.

Fix (one change): in `report.py`, make `day_label` use UTC explicitly:

```python
from datetime import datetime, timezone
...
return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
```

Status: change applied by reading only. **Not yet verified by running `./run.sh`**, because Bash was denied. Expected result: both tests pass.

## 6. Verification log

- [pending] `./run.sh` after fix — not run (Bash permission denied).
