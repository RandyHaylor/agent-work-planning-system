# Troubleshooting: `./run.sh` fails

## 1. Error (verbatim, first run of `./run.sh`)

```
test_connection_string (test_db.DbTest) ... ERROR
test_debug_from_local (test_db.DbTest) ... ok

======================================================================
ERROR: test_connection_string (test_db.DbTest)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/home/aikenyon/.cache/claude-code/tmp/claude-1000/-home-aikenyon-ai-skills-agents-resources-agent-work-planning-system/ed69a354-e825-48f0-841a-c1aa934455f3/scratchpad/trials/config_merge__B__3/work/test_db.py", line 10, in test_connection_string
    self.assertEqual(db.connection_string(cfg), "postgres://base/app?pool=20")
  File "/home/aikenyon/.cache/claude-code/tmp/claude-1000/-home-aikenyon-ai-skills-agents-resources-agent-work-planning-system/ed69a354-e825-48f0-841a-c1aa934455f3/scratchpad/trials/config_merge__B__3/work/db.py", line 3, in connection_string
    return f"{db['url']}?pool={db['pool']}"
KeyError: 'url'

----------------------------------------------------------------------
Ran 2 tests in 0.000s

FAILED (errors=1)
EXIT=1
```

## 2. Research (evidence read; no web access)

Files read:
- `run.sh`: runs `python3 -m unittest -v` from its own directory. Nothing custom.
- `db.py`: `connection_string(cfg)` reads `cfg["database"]`, then `db["url"]` and `db["pool"]`. It points at line 3 in the traceback.
- `settings.py`: `load()` reads `config.json`, then, if `config.local.json` exists, calls `cfg.update(local)` (line 13). `update` is a shallow merge: a top-level key in the local file replaces the whole value.
- `test_db.py`: expects `db.connection_string(settings.load()) == "postgres://base/app?pool=20"`. So `url` must come from the base file and `pool` from the local file, which requires a merge of the `database` object.
- `config.json`: `"database": {"url": "postgres://base/app", "pool": 5}`, `"debug": false`.
- `config.local.json`: `"database": {"pool": 20}`, `"debug": true`. It has no `url`.

Error meaning: `KeyError: 'url'` means the merged `cfg["database"]` has no `url`. The only place `database` is replaced is `cfg.update(...)` in `settings.py`. Line 3 of `db.py` is the first lookup of `url`, which matches the traceback.

Limitation: Bash was denied by the permission mode partway through, so I could not re-run `./run.sh` after the change or inspect git history or `__pycache__`. Verification below is by reading only.

## 3. Candidate causes

| # | Candidate | Likelihood | Cost to rule out | Check and result |
|---|-----------|-----------|------------------|------------------|
| A | `settings.load` shallow-merges, so `config.local.json`'s `database` replaces the base `database` and drops `url` | high | by logic | Read `settings.py` line 13 and `config.local.json`. Local has `database` without `url`, and `update` replaces the key. **Consistent with the error.** Not yet confirmed by running. |
| B | `config.json` is missing `url` (bad base config) | low | trivial | Read `config.json`. It contains `"url": "postgres://base/app"`. **Ruled out.** |
| C | `db.py` uses the wrong key or nesting | low | by logic | Read `db.py`. It reads `cfg["database"]["url"]`, the same shape as `config.json`. The test expects this exact output. **Ruled out** as a standalone bug. Its behaviour is correct for a complete merged config. |
| D | Stale `__pycache__` holds old code | low | trivial | Would need a directory listing or delete; Bash denied. Not checked. It would not explain the error, since the `.py` sources are what the traceback quotes. |

Order checked: A (by logic), B (read), C (read), D (not checked, low likelihood and not the cause given A).

## 4. Root cause

`settings.load()` merges config files with a shallow `dict.update`. Nested objects are replaced, not merged. The local override supplies only `pool`, so the `url` from the base config is lost. The fix belongs in `settings.py`: merge nested dicts recursively, so `config.local.json` overrides individual keys.

Not changing: `run.sh`, `test_db.py`, `db.py` (correct for a full config), and the config JSON files.

## 5. Changes and results

Change 1: `settings.py`. Replace the shallow `cfg.update(...)` with a recursive merge.
- Run after change: **not possible** (Bash denied). Expected result from reading: `database` becomes `{"url": "postgres://base/app", "pool": 20}`, `debug` becomes `true`. `test_connection_string` gives `postgres://base/app?pool=20`; `test_debug_from_local` still passes.
- Trace by reading: `_merge(cfg, local)`. Key `database`: both sides are dicts, so recurse. `pool` 5 is replaced by 20. `url` is not in the override, so it stays. Key `debug`: not a dict, so it is set to `true`. Result matches the expected output.
- Status: **unverified by execution.** Run `./run.sh` to confirm.
