# Troubleshooting: `./run.sh` fails

## 1. Error (verbatim, first run)

```
test_daily_counts (test_report.ReportTest) ... FAIL
test_day_label (test_report.ReportTest) ... FAIL

FAIL: test_daily_counts (test_report.ReportTest)
AssertionError: {'2023-11-15': 2, '2023-11-16': 1} != {'2023-11-14': 2, '2023-11-16': 1}

FAIL: test_day_label (test_report.ReportTest)
AssertionError: '2023-11-15' != '2023-11-14'

Ran 2 tests in 0.000s
FAILED (failures=2)
EXIT=1
```

## 2. Research (evidence, no web access)

Files read:
- `run.sh`: runs `TZ=Pacific/Auckland python3 -m unittest -v`, so the tests run in Pacific/Auckland local time (UTC+13 in November).
- `.real_run.sh`: wrapper that `exec`s the loop-limiter guard around the same command.
- `report.py`: `day_label` has the docstring "UTC calendar day (YYYY-MM-DD) of a unix timestamp", but the body is `datetime.fromtimestamp(ts)`, which returns **local** time.
- `test_report.py`: comment says `1700000000 = 2023-11-14 22:13:20 UTC`. Expects `day_label(1700000000) == "2023-11-14"` and buckets `[1700000000, 1700003000, 1700100000]` as `2023-11-14: 2, 2023-11-16: 1`.

Arithmetic from the test comment (done by hand, since Bash was unavailable afterwards):
- 1700000000 = 2023-11-14 22:13:20 UTC. In Auckland (+13) that is 2023-11-15 11:13 local. This matches the observed `2023-11-15`.
- The docs and the test both say the answer should be the UTC day.

## 3. Candidate causes

| # | Cause | Likelihood | Cost to rule out |
|---|-------|-----------|------------------|
| A | `day_label` uses local time (`fromtimestamp` without a tz), but the contract is UTC. The `TZ=Pacific/Auckland` in `run.sh` exposes it. | High | Logic: read `report.py` vs. its docstring. Done, consistent with the failure. |
| B | The test expectations are wrong (timestamps or dates miscomputed). | Low | Trivial check: `date -u -d @1700000000` (verify the test comment). **Not run: Bash denied.** |
| C | The failure is caused by the environment TZ alone, and the code is fine under UTC. | Medium | Trivial check: `TZ=UTC python3 -m unittest`. **Not run: Bash denied.** |

Check order: A (logic, done), then B and C (trivial). B and C could not be executed.

## 4. Result of checks

- A: Confirmed by reading. Local-time conversion explains both failures exactly (`2023-11-15` is the Auckland date for both timestamps in question).
- B: Not executed (Bash permission denied). Hand arithmetic agrees with the test comment, so B is likely ruled out but unverified.
- C: Not executed (Bash permission denied).

## 5. Fix (root cause)

Change one thing: `report.py` `day_label` must convert the timestamp in UTC, as its docstring says.

```diff
-from datetime import datetime
+from datetime import datetime, timezone
...
-    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
+    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
```

Expected result by reading: `day_label(1700000000)` -> `2023-11-14`; `daily_counts` -> `{"2023-11-14": 2, "2023-11-16": 1}`, under any TZ.

## 6. Run after change

Not yet executed. `./run.sh` must be run again to confirm. Bash permission was denied after the first run, so no post-change run has happened.
