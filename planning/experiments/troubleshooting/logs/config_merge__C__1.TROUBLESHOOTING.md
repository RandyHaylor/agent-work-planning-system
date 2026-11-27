# Troubleshooting: `./run.sh` fails

## 1. Error (verbatim, first run of `./run.sh`)

```
test_connection_string (test_db.DbTest) ... ERROR
test_debug_from_local (test_db.DbTest) ... ok

======================================================================
ERROR: test_connection_string (test_db.DbTest)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/home/aikenyon/.cache/claude-code/tmp/claude-1000/-home-aikenyon-ai-skills-agents-resources-agent-work-planning-system/ed69a354-e825-48f0-841a-c1aa934455f3/scratchpad/trials/config_merge__C__1/work/test_db.py", line 10, in test_connection_string
    self.assertEqual(db.connection_string(cfg), "postgres://base/app?pool=20")
  File "/home/aikenyon/.cache/claude-code/tmp/claude-1000/-home-aikenyon-ai-skills-agents-resources-agent-work-planning-system/ed69a354-e825-48f0-841a-c1aa934455f3/scratchpad/trials/config_merge__C__1/work/db.py", line 3, in connection_string
    return f"{db['url']}?pool={db['pool']}"
KeyError: 'url'

----------------------------------------------------------------------
Ran 2 tests in 0.000s

FAILED (errors=1)
EXIT=1
```

## 2. Research (repo files only; no web access; no docs or changelog exist in the repo)

Files read as evidence:
- `run.sh` – wrapper that `exec`s a loop limiter (`guard/loopguard.py`, outside the project; not inspected) around `.real_run.sh`.
- `.real_run.sh` – `cd`s to its directory and runs `python3 -m unittest -v`.
- `test_db.py` – expects `db.connection_string(settings.load())` == `"postgres://base/app?pool=20"`, and `settings.load()["debug"]` truthy.
- `db.py` – `connection_string` reads `cfg["database"]["url"]` and `cfg["database"]["pool"]`. Traceback line 3 matches this.
- `settings.py` – `load()` reads `config.json`, then does `cfg.update(json.loads(config.local.json))`. `dict.update` is a shallow merge.
- `config.json` – `{"database": {"url": "postgres://base/app", "pool": 5}, "debug": false}`.
- `config.local.json` – `{"database": {"pool": 20}, "debug": true}`. It has no `url`.

Error-text analysis: `KeyError: 'url'` is raised at `db.py:3` when `cfg["database"]` lacks `"url"`. The only code that builds `cfg["database"]` is `settings.load()`.

## 3. Candidate causes

| # | Candidate | Likelihood | Cost to rule out | Check | Result |
|---|-----------|------------|------------------|-------|--------|
| 1 | `settings.load()` shallow-merges `config.local.json`, so the local `"database"` object replaces the base one and drops `url` | high | by logic (already read) | Read `settings.py` and `config.local.json` | **Consistent with the error.** `dict.update` replaces top-level key `"database"` with `{"pool": 20}`, leaving no `url`. This explains the traceback exactly. |
| 2 | `config.local.json` is malformed or is missing `url` as data | medium | trivial | Read `config.local.json` | Valid JSON. It intentionally overrides only `pool`, so the data is not wrong. The merge is the problem, not the file. Ruled out as the root cause. |
| 3 | `db.py` uses the wrong key names or structure | low | trivial | Read `db.py` and `config.json` | Keys `database`/`url`/`pool` match `config.json`. Ruled out. |
| 4 | Test expectation is wrong (`postgres://base/app?pool=20` is not the intended result) | low | trivial | Read `test_db.py` | The expectation is consistent with a deep merge (url from base, pool from local). Test is correct; not to be edited. Ruled out. |
| 5 | Stale `__pycache__` bytecode | low | by logic | Python revalidates bytecode against source mtime/size; `db.py` and `settings.py` were read directly | Not checked by running. Unlikely; ruled out by logic. |

Order of elimination: 3, 4, 2, 5 (cheap, by reading), then 1 (the fix target).

## 4. Root cause

`settings.load()` uses a shallow `dict.update` for the layering. A nested `"database"` section in the local override discards the base `"database"` section instead of merging into it.

Fix (one change, in `settings.py`): replace the shallow update with a recursive merge so nested dicts are merged key by key. This is the root-cause fix, not a change to the test or to `db.py`.

## 5. Change log

- Run 1 (before any change): `./run.sh` → FAILED (errors=1), `KeyError: 'url'`, exit 1.
- Change 1: `settings.py` – replaced `cfg.update(local)` with a recursive `_deep_merge(cfg, local)`. Only this file changed (`run.sh` and test files untouched).
- Run 2 (after change 1): `./run.sh` → `test_connection_string ... ok`, `test_debug_from_local ... ok`, `Ran 2 tests`, `OK`, exit 0.
