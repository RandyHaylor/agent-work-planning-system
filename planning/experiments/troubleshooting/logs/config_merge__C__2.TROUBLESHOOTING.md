# Troubleshooting: `./run.sh` fails

## 1. Error (verbatim, first run)

```
test_connection_string (test_db.DbTest) ... ERROR
test_debug_from_local (test_db.DbTest) ... ok

======================================================================
ERROR: test_connection_string (test_db.DbTest)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/home/aikenyon/.cache/claude-code/tmp/claude-1000/-home-aikenyon-ai-skills-agents-resources-agent-work-planning-system/ed69a354-e825-48f0-841a-c1aa934455f3/scratchpad/trials/config_merge__C__2/work/test_db.py", line 10, in test_connection_string
    self.assertEqual(db.connection_string(cfg), "postgres://base/app?pool=20")
  File "/home/aikenyon/.cache/claude-code/tmp/claude-1000/-home-aikenyon-ai-skills-agents-resources-agent-work-planning-system/ed69a354-e825-48f0-841a-c1aa934455f3/scratchpad/trials/config_merge__C__2/work/db.py", line 3, in connection_string
    return f"{db['url']}?pool={db['pool']}"
KeyError: 'url'

----------------------------------------------------------------------
Ran 2 tests in 0.000s

FAILED (errors=1)
EXIT=1
```

## 2. Research (evidence, no web access)

Only the error text and files in this repo were examined. The repo has no docs, changelog, or README.

- `run.sh` – wrapper that execs the loop limiter (`guard/loopguard.py`), which runs `.real_run.sh`.
- `.real_run.sh` – `cd`s to its directory and runs `python3 -m unittest -v`.
- `test_db.py` – line 10 expects `db.connection_string(settings.load())` == `"postgres://base/app?pool=20"`; line 13 expects `settings.load()["debug"]` to be truthy.
- `db.py` – `connection_string` reads `cfg["database"]`, then `db['url']` and `db['pool']`. The `KeyError: 'url'` is raised at line 3, so `cfg["database"]` exists but has no `"url"` key.
- `settings.py` – `load()` reads `config.json`, then does `cfg.update(json.loads(config.local.json))`.
- `config.json` – `{"database": {"url": "postgres://base/app", "pool": 5}, "debug": false}`.
- `config.local.json` – `{"database": {"pool": 20}, "debug": true}`.

Reading these together: `dict.update` is a top-level replace. The local file's `"database"` key replaces the whole base `"database"` object, so the `url` from the base is lost.

## 3. Candidate causes

| # | Cause | Likelihood | Cost to rule out | Order |
|---|-------|-----------|------------------|-------|
| A | `settings.load` uses a shallow `dict.update`, so the local `"database"` object replaces the base one and drops `"url"`. | High | By logic (reading `settings.py` against the traceback and the two JSON files) | 1 |
| B | `config.local.json` is malformed or has the wrong structure (for example, `database` isn't an object). | Low | Trivial (read the file) | 2 |
| C | `db.py` expects a different key layout than `config.json` uses. | Low | Trivial (read `db.py` against `config.json`) | 3 |
| D | Stale `__pycache__/` bytecode is being loaded. | Low | By logic (CPython checks source mtime/size before using cached `.pyc`; `__pycache__` is dated after the sources) | 4 |

## 4. Results of checks

- **A (shallow merge): CONFIRMED by logic.** `settings.load()` returns `{"database": {"pool": 20}, "debug": true}`. `db.connection_string` then fails on `db['url']`, which matches the traceback exactly. The second test (`debug` from local) passes because top-level keys are merged correctly, which is consistent with A and rules out a general load failure.
- **B (malformed local JSON): RULED OUT.** `config.local.json` is valid JSON with the expected `database` object and `debug` key. It loads without error, since the failure is a `KeyError`, not a `JSONDecodeError`.
- **C (db.py key mismatch): RULED OUT.** `db.py` reads `database.url` and `database.pool`, which are the keys `config.json` defines. The expected string `postgres://base/app?pool=20` shows `url` should come from base and `pool` from local, which is a nested merge.
- **D (stale bytecode): RULED OUT by logic.** The traceback shows the current `db.py` and `settings.py` source lines (line 3 of `db.py` matches the file). Stale bytecode would not produce a line-accurate traceback of the current source.

## 5. Fix plan

Root cause: `settings.load` merges only at the top level. Fix: make the merge recursive so nested objects like `database` are merged key by key. Change only `settings.py`. Do not edit `run.sh` or the test files.

## 6. Change log

_(Recorded below after each change and each run.)_

- Run 1 (before any change): FAILED, `KeyError: 'url'`, EXIT=1.
- Change 1: `settings.py` – replaced the top-level `cfg.update(...)` with a recursive `_deep_merge(...)`, so the local `database` object is merged into the base `database` object instead of replacing it. No other files changed.
- Run 2 (after change 1): PASSED, both tests `ok`, `OK`, EXIT=0.
