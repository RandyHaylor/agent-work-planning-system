# TROUBLESHOOTING: `./run.sh` fails

## 1. Error (verbatim, run 1, before any code change)

```
test_count (test_importer.ImporterTest) ... FAIL
test_total (test_importer.ImporterTest) ... FAIL

======================================================================
FAIL: test_count (test_importer.ImporterTest)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/home/aikenyon/.cache/claude-code/tmp/claude-1000/-home-aikenyon-ai-skills-agents-resources-agent-work-planning-system/ed69a354-e825-48f0-841a-c1aa934455f3/scratchpad/trials/vendored_api__C__2/work/test_importer.py", line 8, in test_count
    self.assertEqual(len(importer.load_readings()), 4)
AssertionError: 3 != 4

======================================================================
FAIL: test_total (test_importer.ImporterTest)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/home/aikenyon/.cache/claude-code/tmp/claude-1000/-home-aikenyon-ai-skills-agents-resources-agent-work-planning-system/ed69a354-e825-48f0-841a-c1aa934455f3/scratchpad/trials/vendored_api__C__2/work/test_importer.py", line 11, in test_total
    self.assertEqual(importer.total(importer.load_readings()), 50)
AssertionError: 38 != 50

----------------------------------------------------------------------
Ran 2 tests in 0.000s

FAILED (failures=2)
```

Exit code: 1

## 2. Research (error text only; no web access)

Evidence reviewed:
- `run.sh` and `.real_run.sh`: `run.sh` is a loop-limiter wrapper that execs `loopguard.py`; `.real_run.sh` runs `python3 -m unittest -v` from the script directory. The failure is from the unittest run itself, not the wrapper.
- `test_importer.py`: expects `load_readings()` to return 4 rows and `total()` to be 50.
- `importer.py`: `load_readings()` calls `tinycsv.read_rows(Path(path).read_text())` and converts each row to `(name, int(value))`. `total()` sums the values.
- `data/readings.csv`: 4 lines, no header line:
  ```
  sensor-a,12
  sensor-b,7
  sensor-c,30
  sensor-d,1
  ```
  Sum of all four values = 50, which is the test's expected total.
- `vendor/tinycsv/__init__.py`: `__version__ = "2.0.0"`. `read_rows(text, sep=",", header=True)`. With `header=True` it discards the first non-blank line.
- `vendor/tinycsv/CHANGELOG.md`: "2.0.0 — BREAKING: `read_rows(header=...)` now defaults to `True` (was `False`). Pass `header=False` for files without a header line." 
- `vendor/__init__.py`: empty.

Reading the evidence: the 3-row count and the 38 total both equal the data with the first row (`sensor-a,12`) removed (50 − 12 = 38). The caller was written for tinycsv < 2.0 (where header defaulted to False) and was not updated for the 2.0.0 default change.

## 3. Candidate causes

| # | Candidate | Likelihood | Cost to rule out | Check |
|---|-----------|------------|------------------|-------|
| A | `importer.py` relies on the pre-2.0 `read_rows` default; the CSV has no header, so `header=True` drops `sensor-a,12`. | High | Logic (cheapest) | Arithmetic: 50 − 12 = 38 and 4 − 1 = 3 match both failures exactly. The changelog confirms the default changed. **Result: consistent with all evidence. Pending the fix test.** |
| B | Blank or whitespace-only lines in `readings.csv` are being dropped, so rows go missing. | Low | Trivial (read the file) | Read of `data/readings.csv` shows exactly 4 non-blank lines and no blank lines inside the data. **Result: ruled out.** (Note: `tinycsv` skips blank lines by design since 1.4.0, but there are none to skip.) |
| C | The test expectations are wrong (4 rows / 50). | Low | Logic | The expectations match the 4 data rows and their sum of 50 exactly, so the data and tests agree. Test files must not be edited anyway. **Result: ruled out.** |
| D | A stale `__pycache__` or a wrong `tinycsv` on the import path is being loaded. | Low | Trivial (inspect the pycache and import path) | `vendor/tinycsv/__init__.py` reports 2.0.0 and that is the version the changelog describes. The `.pyc` files are `cpython-310` and are regenerated from source when the source mtime changes, so they cannot pin an old behaviour. **Result: ruled out as the cause.** |

Check order: B (trivial), D (trivial), C (logic), A (logic plus arithmetic). A is the only candidate consistent with every observation, so it is the root cause.

## 4. Fix plan

Fix the root cause in the caller, not the symptom: `importer.py` should state that the file has no header (`header=False`). Do not edit the vendored library, the data file, the tests, or `run.sh`.

- Change 1: `importer.py` line 9 — `tinycsv.read_rows(Path(path).read_text())` → `tinycsv.read_rows(Path(path).read_text(), header=False)`.

## 5. Change log

| Step | Action | Result of `./run.sh` |
|------|--------|----------------------|
| 0 | Baseline, no changes | FAIL: `test_count` 3 != 4; `test_total` 38 != 50; exit 1 |
| 1 | `importer.py`: pass `header=False` to `read_rows` | PASS: `test_count ... ok`, `test_total ... ok`, `Ran 2 tests ... OK`, exit 0 |

Files not changed: `run.sh`, `.real_run.sh`, `test_importer.py`, `data/readings.csv`, `vendor/`.
