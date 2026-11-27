# TROUBLESHOOTING: `./run.sh` fails

## 1. Error (verbatim, first run of `./run.sh`)

```
test_connection_string (test_db.DbTest) ... ERROR
test_debug_from_local (test_db.DbTest) ... ok

======================================================================
ERROR: test_connection_string (test_db.DbTest)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/home/aikenyon/.cache/claude-code/tmp/claude-1000/-home-aikenyon-ai-skills-agents-resources-agent-work-planning-system/ed69a354-e825-48f0-841a-c1aa934455f3/scratchpad/trials/config_merge__B__1/work/test_db.py", line 10, in test_connection_string
    self.assertEqual(db.connection_string(cfg), "postgres://base/app?pool=20")
  File "/home/aikenyon/.cache/claude-code/tmp/claude-1000/-home-aikenyon-ai-skills-agents-resources-agent-work-planning-system/ed69a354-e825-48f0-841a-c1aa934455f3/scratchpad/trials/config_merge__B__1/work/db.py", line 3, in connection_string
    return f"{db['url']}?pool={db['pool']}"
KeyError: 'url'

----------------------------------------------------------------------
Ran 2 tests in 0.001s

FAILED (errors=1)
EXIT=1
```

## 2. Research (repo files only; no web access)

Files read as evidence:
- `run.sh`: `cd`s to its own directory and runs `python3 -m unittest -v`.
- `test_db.py`: expects `settings.load()` merged with `db.connection_string()` to produce `"postgres://base/app?pool=20"`, and expects `settings.load()["debug"]` to be truthy.
- `db.py`: `connection_string(cfg)` reads `cfg["database"]["url"]` and `cfg["database"]["pool"]`.
- `settings.py`: `load()` reads `config.json`, then does `cfg.update(json.loads(config.local.json))`.
- `config.json`: `{"database": {"url": "postgres://base/app", "pool": 5}, "debug": false}`.
- `config.local.json`: `{"database": {"pool": 20}, "debug": true}`.

Relevant observation from the error: the traceback's KeyError is raised in `db.py` line 3, so `cfg["database"]` exists but has no `url` key. The only place the `database` dict is built is `settings.load()`.

The `KeyError` is not on `pool`, so the merged `database` dict has `pool` but not `url`. That matches a top-level `dict.update()` replacing the whole `database` object with the local one.

## 3. Candidate causes

| # | Candidate cause | Likelihood | Cost to rule out |
|---|---|---|---|
| A | `settings.load()` uses shallow `dict.update()`, so `config.local.json`'s `database` object replaces the base `database` object entirely, dropping `url`. | High | Logic (already reads from the traceback and both JSON files) |
| B | `db.connection_string()` reads the wrong key (e.g., `url` should be under a different name). | Low | Trivial check: compare key names in `db.py` against `config.json` |
| C | `config.local.json` is not being loaded at all (path or `HERE` resolution bug). | Low | Logic: `test_debug_from_local` passes, which requires the local file to be loaded, so this is ruled out |

Order of checks: A (logic), then B (trivial), then C (logic, already settled).

## 4. Check results

- **A: Confirmed by logic.** `config.local.json` has a `database` key whose value is `{"pool": 20}` with no `url`. Python's `dict.update()` replaces top-level keys wholesale, so after `cfg.update(local)` the `database` value is `{"pool": 20}`. `db.py` then fails on `db['url']`, which matches the `KeyError: 'url'` exactly. The `debug` test passes because `debug` is a top-level key and is correctly overridden.
- **B: Ruled out.** `db.py` uses `url` and `pool`, which are the same key names as in `config.json`. The `KeyError` is for a key that is absent from the data, not one that is misnamed.
- **C: Ruled out.** `test_debug_from_local` passes, so `config.local.json` is loaded.

Conclusion: root cause is candidate A, the shallow merge in `settings.py`. The fix belongs in `settings.py` (a recursive merge), not in `db.py` (which is correct) and not in the test or JSON data.

## 5. Changes and results

### Change 1: `settings.py`, replace shallow `cfg.update(...)` with a recursive `_deep_merge(...)`

- Rationale: candidate A. Nested dicts (`database`) are merged key-by-key, so the base `url` is kept and the local `pool` overrides only `pool`.
- Result of `./run.sh`:

```
test_connection_string (test_db.DbTest) ... ok
test_debug_from_local (test_db.DbTest) ... ok

----------------------------------------------------------------------
Ran 2 tests in 0.000s

OK
EXIT=0
```

Status: **passing**. No further changes made. `run.sh`, `test_db.py`, `db.py`, and the JSON configs were not modified.
