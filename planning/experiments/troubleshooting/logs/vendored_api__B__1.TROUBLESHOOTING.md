# Troubleshooting: `./run.sh` failing

## 1. Error (verbatim, first run of `./run.sh`, exit 1)

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
Ran 2 tests in 0.001s

FAILED (failures=2)
```

## 2. Research (files read; no web access, no outside guesses)

- `run.sh`: runs `python3 -m unittest -v` from the script's directory.
- `test_importer.py`: expects 4 readings and a total of 50.
- `importer.py`: `load_readings()` calls `tinycsv.read_rows(text)` with no `header` argument, then converts each row to `(name, int(value))`.
- `vendor/tinycsv/__init__.py`: `__version__ = "2.0.0"`. `read_rows(text, sep=",", header=True)` drops the first non-blank line when `header` is True.
- `vendor/tinycsv/CHANGELOG.md`: 2.0.0 entry says "BREAKING: `read_rows(header=...)` now defaults to `True` (was `False`). Pass `header=False` for files without a header line." 1.4.0 entry: blank lines are skipped.
- `data/readings.csv` (read via file tool): 4 lines, no header line:
  ```
  sensor-a,12
  sensor-b,7
  sensor-c,30
  sensor-d,1
  ```
- `vendor/__init__.py`: empty (package marker only).

## 3. Candidate causes

| # | Candidate | Likelihood | Cost to rule out |
|---|-----------|-----------|------------------|
| A | `importer.py` uses the 2.0.0 default `header=True`, but `readings.csv` has no header, so the first data row (`sensor-a,12`) is discarded. | high | by logic |
| B | The vendored `tinycsv` is an older version whose default is `header=False`, or a different copy is being imported. | low | trivial check |
| C | Data file is empty, has a wrong path, or has malformed rows. | low | trivial check |
| D | Stale `__pycache__` or whitespace/blank-line parsing problem. | low | trivial check |

## 4. Checks (cheapest first)

1. **A, by logic:** Dropping `sensor-a,12` leaves 3 rows, which matches `3 != 4`. The remaining sum is 7 + 30 + 1 = 38, which matches `38 != 50`. Dropping the first row explains both failures exactly. **Result: consistent with A (supports the cause).**
2. **B, trivial check:** `vendor/tinycsv/__init__.py` reads `__version__ = "2.0.0"`, and its signature defaults `header=True`. No other `tinycsv` copy is on the path (the only vendored package is `vendor/tinycsv`). **Result: ruled out. The version is the one that has the header default, so B is not a separate cause; it is the mechanism of A.**
3. **C, trivial check:** `data/readings.csv` exists and has 4 non-empty lines. The `load_readings` path defaults to it via `Path(__file__).parent`. **Result: ruled out.**
4. **D, trivial check (by reading):** The data lines show no blank lines or extra whitespace. `read_rows` already skips blank lines. The `.pyc` files are for cpython-310 and are invalidated by source mtime. **Result: not expected to matter; not confirmed by running.**

## 5. Root cause

`tinycsv` 2.0.0 (BREAKING change, documented in its CHANGELOG) treats the first line as a header by default. `importer.py` relied on the old default, and `data/readings.csv` is a headerless file. The fix belongs in the caller, since the data file's format is headerless and `run.sh`, the tests, and the vendored library should not change.

## 6. Planned change (one change)

In `importer.py`, pass `header=False` to `tinycsv.read_rows`, as the CHANGELOG recommends for headerless files.

## 7. Change applied

`importer.py` `load_readings()`: `tinycsv.read_rows(Path(path).read_text())` changed to `tinycsv.read_rows(Path(path).read_text(), header=False)`. This is the only change; `run.sh`, the tests, the data, and `vendor/` are untouched.

## 8. Re-run result

**Not verified.** The Bash tool was denied (permission mode "don't ask") on the first inspection call and was not retried, so `./run.sh` could not be re-run after the change. Expected by logic: 4 rows, total 50, both tests pass. To confirm: run `./run.sh` in the work directory and expect `Ran 2 tests ... OK`.
