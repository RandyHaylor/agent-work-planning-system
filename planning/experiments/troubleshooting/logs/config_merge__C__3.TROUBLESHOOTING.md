# TROUBLESHOOTING: `./run.sh` fails

## 1. Error (verbatim, run #1, before any change)

```
test_connection_string (test_db.DbTest) ... ERROR
test_debug_from_local (test_db.DbTest) ... ok

======================================================================
ERROR: test_connection_string (test_db.DbTest)
----------------------------------------------------------------------
Traceback (most recent call last):
  File ".../work/test_db.py", line 10, in test_connection_string
    self.assertEqual(db.connection_string(cfg), "postgres://base/app?pool=20")
  File ".../work/db.py", line 3, in connection_string
    return f"{db['url']}?pool={db['pool']}"
KeyError: 'url'

----------------------------------------------------------------------
Ran 2 tests in 0.000s

FAILED (errors=1)
```

Exit status: 1.

## 2. Research (read-only; no web access)

Files read as evidence:
- `run.sh`: wrapper that execs `guard/loopguard.py` with the project dir and `guard/state.json`. It does not affect test logic.
- `.real_run.sh`: `cd`s to its dir and runs `python3 -m unittest -v 2>&1`. The test run is the real command.
- `db.py` (lines 1-3): `connection_string(cfg)` reads `cfg["database"]`, then `db['url']` and `db['pool']`. Line 3 is the line in the traceback.
- `settings.py` (lines 7-14): `load()` reads `config.json`, then for `config.local.json` calls `cfg.update(json.loads(...))`. `dict.update` is shallow: a top-level key present in the local file replaces the base value entirely.
- `config.json`: `"database": {"url": "postgres://base/app", "pool": 5}`, `"debug": false`.
- `config.local.json`: `"database": {"pool": 20}`, `"debug": true`.
- `test_db.py`: expects `connection_string(settings.load()) == "postgres://base/app?pool=20"`, and `settings.load()["debug"]` is true.
- The `unittest` and `dict.update` behaviour is standard Python; I did not look at any changelog because none is in the repo.
- Not read: `guard/loopguard.py` and `guard/state.json` (outside the fix; not needed to explain the error).

## 3. Candidate causes

| # | Candidate | Likelihood | Cost to rule out |
|---|-----------|------------|------------------|
| A | `settings.load()` uses shallow `dict.update`, so the local `"database"` replaces the base `"database"` and the `url` key is lost. | High | Logic (cheap) |
| B | `config.local.json` is not being loaded (wrong path or missing file). | Low | Trivial (test output) |
| C | `db.connection_string` has the wrong key names or format. | Low | Logic (cheap) |
| D | Stale `__pycache__` bytecode is running old code. | Low | Logic (line numbers in traceback match current source) |

## 4. Checks (cheapest first)

- **B (trivial, from test output):** `test_debug_from_local` passes and prints `ok`. That means `config.local.json` is found and `debug` is read from it. Result: **ruled out.**
- **C (logic):** The traceback is at `db.py:3` on `db['url']`. The `KeyError` is for `'url'`, not for the key name or format of `pool`. The expected string `postgres://base/app?pool=20` matches the format in `db.py`. Result: **ruled out** as the cause.
- **D (logic):** The traceback line `return f"{db['url']}?pool={db['pool']}"` matches the current `db.py` source exactly, so the bytecode is not stale in a way that matters. Result: **ruled out.**
- **A (logic):** Walk through `load()`. `cfg` = base dict, `cfg.update({"database": {"pool": 20}, "debug": true})`. Result: `cfg["database"] == {"pool": 20}`, with no `url`. `db['url']` then raises `KeyError: 'url'`. This matches the traceback exactly. Result: **confirmed as the root cause.**

## 5. Root cause

`settings.load()` does a shallow merge. Local overrides replace whole sections, so a partial `database` override (only `pool`) drops the base `url`. The correct fix is a recursive (deep) merge in `settings.py`, so that nested keys from the local file override only the keys they set.

## 6. Planned change (one change at a time)

1. Change `settings.py` to deep-merge `config.local.json` into the base config. Do not change `run.sh`, the test files, or `config.json`/`config.local.json`.
2. Re-run `./run.sh` and record the result below.

## 7. Run log

| Run | Change | Result |
|-----|--------|--------|
| 1 | None (baseline) | FAILED: `KeyError: 'url'`, exit 1 |
| 2 | Deep merge in `settings.py` (`_deep_merge` recursive; `load()` uses it) | NOT RUN: the Bash tool was denied ("don't ask" mode), so `./run.sh` could not be executed after the change. |

## 8. Verification by hand-trace (not a test run)

Since the command could not be run, I traced `settings.load()` and `db.connection_string()` by reading the code:

1. Base `cfg` = `{"database": {"url": "postgres://base/app", "pool": 5}, "debug": false}`.
2. Local = `{"database": {"pool": 20}, "debug": true}`.
3. `_deep_merge`: `database` is a dict in both, so it recurses and sets `pool = 20`; `url` is kept. `debug` is set to `true`.
4. `cfg["database"] == {"url": "postgres://base/app", "pool": 20}`.
5. `connection_string` returns `postgres://base/app?pool=20`, which matches `test_connection_string`.
6. `test_debug_from_local`: `load()["debug"]` is `true`, so it still passes.

Expected result: both tests pass and `run.sh` exits 0. **This is unconfirmed until `./run.sh` is run.**
