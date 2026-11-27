# Troubleshooting: `./run.sh` fails

## 1. Error (verbatim, first run of `./run.sh`)

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

## 2. Research (no web access; only the error and the code/docs it points at)

Files examined as evidence:
- `run.sh` — runs `python3 -m unittest -v`. Not a cause; it only runs the tests.
- `test_importer.py` — expects 4 rows and a total of 50. Both assertions are plain value checks, not import or setup errors.
- `importer.py` — `load_readings()` calls `tinycsv.read_rows(text)` with no `header` argument, then converts each row to `(name, int(value))`. `total()` sums the values.
- `vendor/tinycsv/__init__.py` — `read_rows(text, sep=",", header=True)`. When `header` is True it drops the first non-blank line.
- `vendor/tinycsv/CHANGELOG.md` — 2.0.0: "BREAKING: `read_rows(header=...)` now defaults to `True` (was `False`). Pass `header=False` for files without a header line." 1.4.0: blank lines are skipped.
- `vendor/__init__.py` — package marker, empty.
- `data/readings.csv` — four lines with no header: `sensor-a,12`, `sensor-b,7`, `sensor-c,30`, `sensor-d,1`.

Key observation: the error is an assertion failure (`3 != 4`, `38 != 50`), not an `ImportError`, so the import path is fine. The CHANGELOG says the 2.0.0 default for `header` changed to True, and the data file has no header. Dropping the first row gives 3 rows and a sum of 7+30+1 = 38, which matches both failures exactly.

## 3. Candidate causes

| # | Candidate | Likelihood | Cost to rule out |
|---|-----------|-----------|------------------|
| A | `importer.py` calls `read_rows` with the new 2.0.0 default `header=True`, but `readings.csv` has no header, so the first data row is dropped. | High | Logic (checked against the file contents and CHANGELOG) |
| B | The data file contains blank lines or whitespace that break parsing. | Low | Trivial (Read of the file showed four clean lines, no blanks) |
| C | Import or module-path problem (wrong `tinycsv` loaded, wrong `importer`). | Low | Logic (failures are assertions, not ImportError; the module imported and ran) |
| D | Stale `__pycache__` (cpython-310 files present) hides a source change. | Low | Trivial (re-run after the edit; Python checks source mtimes) |

Order checked: A is confirmed by logic first, then B, C, and D are ruled out by the cheapest checks.

## 4. Results of checks

- **B (blank lines / whitespace):** Read of `data/readings.csv` shows exactly four non-blank lines and no header. Ruled out.
- **C (import path):** Both tests ran and failed on assertion values, so `importer` and `vendor.tinycsv` imported successfully. Ruled out.
- **A (header default):** Hypothesis predicts 3 rows and total 38. Observed: `3 != 4` and `38 != 50`. Confirmed by logic. Root cause is the header default in the caller, not a defect in the vendored library.
- **D (stale pycache):** Not needed as a distinct check since the failure is explained by A; it will be exercised by the post-fix run.

## 5. Root cause and fix plan

Root cause: `importer.py` relies on the default of `tinycsv.read_rows`, which changed in 2.0.0 from `header=False` to `header=True`. The data file has no header line, so the caller must say so explicitly.

Planned fix (one change): in `importer.py`, call `tinycsv.read_rows(..., header=False)`. This is the documented 2.0.0 API. The vendored library, the data file, the tests, and `run.sh` are left untouched.

## 6. Change log

### Change 1: `importer.py` line 9 — `tinycsv.read_rows(..., header=False)`

Result of `./run.sh` (EXIT=0):

```
test_count (test_importer.ImporterTest) ... ok
test_total (test_importer.ImporterTest) ... ok

----------------------------------------------------------------------
Ran 2 tests in 0.000s

OK
```

Outcome: both failures resolved with one change. Only one change was made, so no further iteration was needed. The failure did not repeat, so no re-research was triggered.
