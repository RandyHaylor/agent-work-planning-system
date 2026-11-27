# Troubleshooting: `./run.sh` failing

## 1. Error (verbatim, first run, before any change)

```
test_count (test_importer.ImporterTest) ... FAIL
test_total (test_importer.ImporterTest) ... FAIL

FAIL: test_count (test_importer.ImporterTest)
  File ".../work/test_importer.py", line 8, in test_count
    self.assertEqual(len(importer.load_readings()), 4)
AssertionError: 3 != 4

FAIL: test_total (test_importer.ImporterTest)
  File ".../work/test_importer.py", line 11, in test_total
    self.assertEqual(importer.total(importer.load_readings()), 50)
AssertionError: 38 != 50

Ran 2 tests in 0.000s
FAILED (failures=2)
EXIT: 1
```

## 2. Research (repo files only; no web access)

Files read as evidence:
- `run.sh`: runs `python3 -m unittest -v` in the script's directory. Not the cause.
- `test_importer.py`: expects 4 rows and a total of 50.
- `importer.py` line 9: `tinycsv.read_rows(Path(path).read_text())`. Calls with the default `header` argument.
- `importer.py` line 3: `from vendor import tinycsv`. Resolves to `vendor/tinycsv/__init__.py`.
- `vendor/tinycsv/__init__.py`: `__version__ = "2.0.0"`. `read_rows(text, sep=",", header=True)` drops the first non-blank line when `header` is True.
- `vendor/tinycsv/CHANGELOG.md`, 2.0.0: "BREAKING: `read_rows(header=...)` now defaults to `True` (was `False`). Pass `header=False` for files without a header line."
- `data/readings.csv`: four lines, no header: `sensor-a,12`, `sensor-b,7`, `sensor-c,30`, `sensor-d,1`. Values sum to 50.
- `vendor/__init__.py`: present (empty package marker, read via Glob listing).

## 3. Candidate causes

| # | Cause | Likelihood | Cost to rule out |
|---|-------|-----------|------------------|
| A | `importer.py` relies on the old `header=False` default. tinycsv 2.0.0 now defaults to `header=True`, so the first data row (`sensor-a,12`) is dropped. | High | Logic |
| B | `data/readings.csv` has a stray or missing header that is wrong. | Low | Trivial (read file) |
| C | The test expectations are wrong (4 rows, sum 50). | Low | Trivial (read file) |
| D | A different `tinycsv` is imported (shadowing or a stale package on the path). | Low | Trivial (check import path) |

Checks, cheapest first:
- **B / C (trivial):** Read `data/readings.csv`. It has 4 data lines and no header, sum 50. The test expectations match the data, so these are not the cause. Eliminated.
- **D (trivial):** `from vendor import tinycsv` is the only import; the `vendor/tinycsv/__init__.py` shown is version 2.0.0. The `__pycache__` contains only `cpython-310` files, nothing that shadows the source. Eliminated.
- **A (logic):** With the header row skipped, the rows are `[7,30,1]` (sum 38, count 3). This matches the failure output exactly (`3 != 4`, `38 != 50`). Dropping `sensor-a,12` (12) from the 50 total gives 38. Confirmed by logic. Not yet confirmed by execution.

Conclusion: cause A. The fix belongs in `importer.py`, which must pass `header=False` because the data file has no header. Vendored `tinycsv` is left unchanged, since the 2.0.0 behavior is intentional and documented.

## 4. Change log

(Each change is recorded below with the command result.)

### Change 1: `importer.py` line 9
- Changed `tinycsv.read_rows(Path(path).read_text())` to `tinycsv.read_rows(Path(path).read_text(), header=False)`.
- Reason: cause A. `data/readings.csv` has no header, and tinycsv 2.0.0 skips the first line by default.
- Result of `./run.sh`: `test_count ... ok`, `test_total ... ok`, `Ran 2 tests`, `OK`, exit 0.
- Only one change was needed; no repeated failure occurred.
