# Troubleshooting: `./run.sh` fails

## 1. Error (verbatim, first run of `./run.sh`)

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
Exit code: 1

## 2. Research (evidence only, no web access)

Files read for evidence:
- `run.sh`: runs `python3 -m unittest -v` in the script's directory.
- `test_db.py`: `test_connection_string` expects `db.connection_string(settings.load())` to equal `"postgres://base/app?pool=20"`. `test_debug_from_local` expects `settings.load()["debug"]` to be true.
- `db.py`: `connection_string` reads `cfg["database"]["url"]` and `cfg["database"]["pool"]`.
- `settings.py`: `load()` reads `config.json`, then, if `config.local.json` exists, calls `cfg.update(json.loads(local))`.
- `config.json`: `{"database": {"url": "postgres://base/app", "pool": 5}, "debug": false}`.
- `config.local.json`: `{"database": {"pool": 20}, "debug": true}`.
- Repo docs: none. The directory contains no README, CHANGELOG, or docs folder.

Reading the error: `KeyError: 'url'` is raised in `db.py:3`, so the `database` dict that reaches `connection_string` has no `url` key.

Reading the data: `dict.update` replaces top-level keys. `config.local.json` has a top-level `"database"` key, so its value `{"pool": 20}` replaces the base `{"url": ..., "pool": 5}` entirely. The merged result is `{"database": {"pool": 20}, "debug": true}`, which has no `url`.

## 3. Candidate causes

| # | Candidate | Likelihood | Cost to rule out | Check |
|---|-----------|------------|------------------|-------|
| A | `settings.load()` shallow-merges, so the local `"database"` object replaces the base one and drops `"url"` | High | Logic | Done (see below) |
| B | `db.py` reads the wrong key name (for example `url` should be something else) | Low | Trivial | Done (see below) |
| C | `config.local.json` is not being read, or is read from the wrong path | Low | Trivial | Done (see below) |
| D | Stale `__pycache__` holds an old version of `settings.py` or `db.py` | Low | Trivial | Not run; see note in section 4 |

Order: cheapest first. A is the most likely and is checked first.

## 4. Check results

- **A (shallow merge):** Confirmed by reading. `settings.py:13` uses `cfg.update(...)`. The local file's `"database"` key replaces the base `"database"` object. The merged dict has `{"pool": 20}` with no `url`, which matches `KeyError: 'url'` exactly. Cause identified.
- **B (wrong key in db.py):** Ruled out. `db.py` uses `url` and `pool`, and `config.json` has both keys under `database`. The key names match.
- **C (local file not read):** Ruled out. `test_debug_from_local` passes in the first run. That test only passes if `config.local.json` is loaded (`debug` is `false` in the base file and `true` only in the local file). So the local file is read correctly.
- **D (stale pycache):** Not run. Bash was denied in this session, so I could not delete or inspect `__pycache__`. The fix does not depend on it. Python recompiles a `.pyc` when the source mtime changes, and the source files were edited, so this is unlikely to matter.

Root cause: A. The fix is a recursive (deep) merge in `settings.py`, so nested dicts are merged key by key and not replaced.

## 5. Changes and results

Change 1: in `settings.py`, added `_deep_merge(base, override)`, which recursively merges nested dicts. `load()` now does `cfg = _deep_merge(cfg, local)` instead of `cfg.update(local)`. No other files changed. `run.sh`, `test_db.py`, and the config files are untouched.
- Result: **pending verification.** Bash was denied for this session, so I could not run `./run.sh` after the change. Expected result: both tests pass, because the merged `database` has `url` from base and `pool` from local (20), and `debug` is `true` from local.
