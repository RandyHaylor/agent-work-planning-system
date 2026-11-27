# Troubleshooting: `./run.sh` fails

## Error (verbatim, first run)

```
test_daily_counts (test_report.ReportTest) ... FAIL
test_day_label (test_report.ReportTest) ... FAIL

FAIL: test_daily_counts (test_report.ReportTest)
  File ".../test_report.py", line 13, in test_daily_counts
    self.assertEqual(counts, {"2023-11-14": 2, "2023-11-16": 1})
AssertionError: {'2023-11-15': 2, '2023-11-16': 1} != {'2023-11-14': 2, '2023-11-16': 1}

FAIL: test_day_label (test_report.ReportTest)
  File ".../test_report.py", line 9, in test_day_label
    self.assertEqual(report.day_label(1700000000), "2023-11-14")
AssertionError: '2023-11-15' != '2023-11-14'

Ran 2 tests in 0.000s
FAILED (failures=2)
EXIT=1
```

## Research (no web access; only the error, the code it points at, and repo files)

Files read:
- `run.sh`: runs `TZ=Pacific/Auckland python3 -m unittest -v`. The failing run is therefore in Auckland local time (UTC+13 on that date).
- `report.py`: `day_label` calls `datetime.fromtimestamp(ts)` with no tz argument, and its docstring says "UTC calendar day".
- `test_report.py`: comment says `1700000000 = 2023-11-14 22:13:20 UTC`, and both tests expect UTC dates.
- No docs, changelogs, or git history exist in this directory (not a git repo).

Observation from the error: the code returns `2023-11-15` for `1700000000`. That is the Auckland local date for 22:13 UTC, which is 11:13 on the 15th. This matches local-time conversion, not UTC.

## Candidate causes

| # | Candidate | Likelihood | Cost to rule out |
|---|-----------|------------|------------------|
| 1 | `fromtimestamp` without a tz uses the process local timezone (set to Pacific/Auckland by run.sh), but the code and tests expect UTC | high | trivial (run the same logic under two TZ values and compare) |
| 2 | The test expectations are wrong (the timestamp-to-date mapping in the comment is incorrect) | low | trivial (compute the UTC date of 1700000000 independently) |
| 3 | Stale `__pycache__` bytecode is masking an edit | low | trivial (run with `-B` and no pyc, see if the result changes) |
| 4 | Python version / `strftime` behavior difference | low | trivial (inspect Python version and call output) |

Checks run in order of cost:

1. **Candidate 1, run under `TZ=UTC`**: `TZ=UTC python3 -m unittest` → `OK`, 2 tests pass. Result: consistent with candidate 1.
2. **Candidate 1, compare conversions in Auckland**: `fromtimestamp(1700000000, timezone.utc)` → `2023-11-14 22:13:20+00:00`; `fromtimestamp(1700000000)` under Auckland → `2023-11-15 11:13:20`. Result: local-time conversion produces the wrong day, UTC-aware conversion produces the expected day. Candidate 1 confirmed.
3. **Candidate 3, bypass bytecode cache**: `TZ=Pacific/Auckland python3 -B -m unittest` → still `FAILED (failures=2)`. Result: cache is not the cause; candidate 3 ruled out.
4. **Candidate 2**: the comment in the test states the UTC date of 1700000000 is 2023-11-14 22:13:20, and check 2 independently confirms that. Result: test expectations are correct; candidate 2 ruled out.
5. **Candidate 4**: Python 3.10.12; the `fromtimestamp` output in check 2 shows correct behavior with `tz=` set. Result: no version issue; candidate 4 ruled out.

Root cause: `day_label` converts the timestamp to the process-local timezone instead of UTC, even though its docstring and tests require UTC. The `TZ=Pacific/Auckland` in `run.sh` exposes this.

## Fix log

### Change 1 (root cause)

`report.py`: `day_label` now passes `tz=timezone.utc` to `datetime.fromtimestamp`, so the date is computed in UTC instead of the process-local zone.

Result of `./run.sh`: `test_daily_counts ... ok`, `test_day_label ... ok`, `Ran 2 tests`, `OK`, EXIT=0.
