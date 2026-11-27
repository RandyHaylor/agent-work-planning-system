# tinycsv changelog

## 2.0.0
- BREAKING: `read_rows(header=...)` now defaults to `True` (was `False`). Pass `header=False` for files without a header line.
- `sep` argument added.

## 1.4.0
- Blank lines are skipped.
