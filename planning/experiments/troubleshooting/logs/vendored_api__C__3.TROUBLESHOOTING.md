# TROUBLESHOOTING: `./run.sh` fails

## 1. Error (verbatim, first run of `./run.sh`)

```
test_count (test_importer.ImporterTest) ... FAIL
test_total (test_importer.ImporterTest) ... FAIL

======================================================================
FAIL: test_count (test_importer.ImporterTest)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/home/aikenyon/.cache/claude-code/tmp/claude-1000/-home-aikenyon-ai-skills-agents-resources-agent-work-planning-system/ed69a354-e825-48f0-841a-c1aa934455f3/scratchpad/trials/vendored_api__C__3/work/test_importer.py", line 8, in test_count
    self.assertEqual(len(importer.load_readings()), 4)
AssertionError: 3 != 4

======================================================================
FAIL: test_total (test_importer.ImporterTest)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/home/aikenyon/.cache/claude-code/tmp/claude-1000/-home-aikenyon-ai-skills-agents-resources-agent-work-planning-system/ed69a354-e825-48f0-841a-c1aa934455f3/scratchpad/trials/vendored_api__C__3/work/test_importer.py", line 11, in test_total
    self.assertEqual(importer.total(importer.load_readings()), 50)
AssertionError: 38 != 50

----------------------------------------------------------------------
Ran 2 tests in 0.000s

FAILED (failures=2)
EXIT=1
```

## 2. Research (evidence reviewed; no web access)

Files and docs read:
- `run.sh` – wrapper; runs `.real_run.sh` through a loop limiter (`guard/loopguard.py`). Not edited.
- `.real_run.sh` – `cd`s to script dir and runs `python3 -m unittest -v`.
- `test_importer.py` – expects `load_readings()` to return 4 rows and `total()` to be 50.
- `importer.py` – `load_readings()` calls `tinycsv.read_rows(text)` with **no** `header` argument, then converts each row to `(name, int(value))`.
- `data/readings.csv` – 4 lines, **no header line**: `sensor-a,12` / `sensor-b,7` / `sensor-c,30` / `sensor-d,1`. No blank lines. Sum = 50.
- `vendor/tinycsv/__init__.py` – `__version__ = "2.0.0"`; `read_rows(text, sep=",", header=True)`; when `header` is True it discards the first non-blank line.
- `vendor/tinycsv/CHANGELOG.md` – "2.0.0 – BREAKING: `read_rows(header=...)` now defaults to `True` (was `False`). Pass `header=False` for files without a header line." and "1.4.0 – Blank lines are skipped."
- `vendor/__init__.py` – empty.

## 3. Candidate causes

| # | Candidate | Likelihood | Cost to rule out | Check |
|---|-----------|------------|------------------|-------|
| A | `tinycsv` 2.0.0 default `header=True` drops the first data row (`sensor-a,12`) because the CSV has no header, and `importer.py` was written against the 1.x default | High | Logic (no execution) | Dropping `sensor-a` gives 3 rows and 50 − 12 = 38, which matches both failures exactly |
| B | `data/readings.csv` is missing rows or has a header line that is wrong | Medium | Trivial (read file) | Read it: 4 data rows, no header |
| C | Vendored library mis-parses lines (blank lines, separator) | Low | Trivial (read library + changelog) | No blank lines in data; `sep=","` default matches; 1.4.0 blank-line handling is not the cause |
| D | Test expectations are wrong (4 rows / total 50) | Low | Logic | Data sums to 12+7+30+1 = 50 with 4 rows, so the expectations match the data |

Order checked: A (logic), B, C, D (cheapest first). A is the only candidate consistent with the observed numbers, and B–D were ruled out by reading the files.

## 4. Check results

- A — Confirmed by logic: the first row is dropped, leaving 3 rows, total 38. Matches `3 != 4` and `38 != 50`.
- B — Ruled out: the file has 4 data rows and no header.
- C — Ruled out: no blank lines, default separator is correct, and the library's skip behavior is as documented.
- D — Ruled out: the test expectations equal the data.
- `vendor/__init__.py` is empty; the import succeeds (the tests executed), so it is not a cause.

## 5. Root cause and fix

Root cause: `importer.py` depends on the pre-2.0.0 `tinycsv` default (`header=False`). The data file has no header, so the 2.0.0 default silently discards the first reading.

Fix (one change): in `importer.py`, pass `header=False` explicitly, as the 2.0.0 changelog instructs for files without a header. Not editing the data file, the test, or `run.sh`.

## 6. Verification log

- Change 1: `importer.py` → `tinycsv.read_rows(Path(path).read_text(), header=False)`.
  - Run `./run.sh`: **NOT RUN.** The Bash tool was denied by the permission mode ("don't ask"), so the command could not be executed in this session. Verification by reading only: with `header=False`, all 4 lines are returned, count = 4 and total = 12+7+30+1 = 50, which matches both assertions. Needs an actual `./run.sh` run to confirm.
