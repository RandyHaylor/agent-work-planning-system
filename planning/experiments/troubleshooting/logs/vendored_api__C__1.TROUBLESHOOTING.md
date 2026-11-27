# TROUBLESHOOTING: `./run.sh` fails

## 1. Error (verbatim, first run)

```
test_count (test_importer.ImporterTest) ... FAIL
test_total (test_importer.ImporterTest) ... FAIL

======================================================================
FAIL: test_count (test_importer.ImporterTest)
----------------------------------------------------------------------
Traceback (most recent call last):
  File ".../work/test_importer.py", line 8, in test_count
    self.assertEqual(len(importer.load_readings()), 4)
AssertionError: 3 != 4

======================================================================
FAIL: test_total (test_importer.ImporterTest)
----------------------------------------------------------------------
Traceback (most recent call last):
  File ".../work/test_importer.py", line 11, in test_total
    self.assertEqual(importer.total(importer.load_readings()), 50)
AssertionError: 38 != 50

----------------------------------------------------------------------
Ran 2 tests in 0.000s

FAILED (failures=2)
EXIT=1
```

## 2. Research (only the error text, and the code/docs it points at)

Files read as evidence:
- `run.sh` - wrapper that execs the loop limiter, which runs the tests.
- `.real_run.sh` - runs `python3 -m unittest -v` in the script's directory. Confirms the tests are plain unittest.
- `test_importer.py` - expects 4 rows and a total of 50 from `importer.load_readings()`.
- `importer.py` - `load_readings()` calls `tinycsv.read_rows(text)` with **no `header` argument**, then converts each row to `(name, int(value))`. `total()` sums the values.
- `data/readings.csv` - 4 data rows (`sensor-a,12`, `sensor-b,7`, `sensor-c,30`, `sensor-d,1`), **no header line**. Sum = 12+7+30+1 = 50. Count = 4.
- `vendor/tinycsv/__init__.py` - `read_rows(text, sep=",", header=True)`. When `header` is True it drops the first non-blank line.
- `vendor/tinycsv/CHANGELOG.md` - `2.0.0`: "BREAKING: `read_rows(header=...)` now defaults to `True` (was `False`). Pass `header=False` for files without a header line." `1.4.0`: blank lines are skipped.
- `vendor/__init__.py` - empty.

Reading of the evidence: the test failure numbers match exactly one row being dropped. Dropping `sensor-a,12` leaves 3 rows summing to 7+30+1 = 38. That is the observed output. The importer relies on the old default (`header=False`), but the vendored library is now 2.0.0, where the default is `True`.

## 3. Candidate causes

| # | Candidate | Likelihood | Cost to rule out | Order |
|---|-----------|-----------|------------------|-------|
| A | `importer.py` omits `header=False`. The vendored tinycsv 2.0.0 default of `header=True` drops the first data row (`sensor-a,12`), which is a breaking change in the changelog. | **High** | By logic: the 3-rows / 38-total numbers equal the dataset with the first row removed. Confirmed by reading the source and changelog. | 1 (cheapest) |
| B | The vendored tinycsv is broken, e.g. it does not split or skip blank lines correctly. | Low | By logic: the source reads correctly, and the splitting and blank-line handling match its docstring and changelog. | 2 |
| C | `data/readings.csv` is malformed, e.g. it has a stray header line, blank lines, or bad values. | Low | By logic: `cat -A` style inspection was blocked, but the Read tool showed exactly 4 clean lines with no header and no whitespace problems. | 3 |
| D | A stale `__pycache__` (`.cpython-310.pyc`) is serving old code. | Low | Trivial: the pyc files are not the source. Python recompiles when the `.py` mtime changes, and the failure is consistent with the current source. | 4 |

Plan: check A first. If A's fix does not make the tests pass, the next candidate is checked in order. Only one change is made at a time.

## 4. Checks

- **Check A (by logic):** Confirmed. The data has no header and the importer uses the default. The changelog says the default changed to `True` in 2.0.0. The arithmetic matches (see section 2). Likelihood high, root cause identified.
- **Check B (by logic):** Ruled out for now. The implementation matches its docstring and changelog. Would only be revisited if A's fix fails.
- **Check C (by logic):** Ruled out for now. The data file shows 4 clean rows with no header.
- **Check D (by logic):** Ruled out for now. The failure is consistent with the current source, and Python recompiles stale bytecode automatically.

## 5. Root cause and fix plan

Root cause: `importer.py` depends on the old `read_rows` default (`header=False`). The vendored `tinycsv` is pinned at 2.0.0, where the default flipped to `True`. The data file has no header line, so the first real reading is silently dropped.

Fix: pass `header=False` explicitly in `importer.py`, matching the file format. This is the correct fix because the data file is correct and the vendored library is pinned and should not be edited. Editing the data to add a fake header would hide the mismatch rather than fix it.

Not changed: `run.sh`, the test files, `data/readings.csv`, and `vendor/`.

## 6. Change log

(Entries are appended below as each change is made and tested.)

### Change 1 (candidate A)
- File: `importer.py`, in `load_readings()`.
- Before: `tinycsv.read_rows(Path(path).read_text())`
- After: `tinycsv.read_rows(Path(path).read_text(), header=False)`
- Run `./run.sh`: `test_count ... ok`, `test_total ... ok`, `Ran 2 tests`, `OK`, EXIT=0.
- Result: **PASS**. Candidates B, C, and D were not needed and were not tested.

Note on the run before this change: the first run (see section 1) was the only failure. No identical failure repeated, so the loop limiter was not triggered.
