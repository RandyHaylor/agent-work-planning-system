# TROUBLESHOOTING: `./run.sh` fails

## 1. Error (verbatim, first run of `./run.sh`)

```
test_session (unittest.loader._FailedTest) ... ERROR

======================================================================
ERROR: test_session (unittest.loader._FailedTest)
----------------------------------------------------------------------
ImportError: Failed to import test module: test_session
Traceback (most recent call last):
  File "/usr/lib/python3.10/unittest/loader.py", line 436, in _find_test_path
    module = self._get_module_from_name(name)
  File "/usr/lib/python3.10/unittest/loader.py", line 377, in _get_module_from_name
    __import__(name)
  File "/home/aikenyon/.cache/claude-code/tmp/claude-1000/-home-aikenyon-ai-skills-agents-resources-agent-work-planning-system/ed69a354-e825-48f0-841a-c1aa934455f3/scratchpad/trials/shadow_secrets__C__3/work/test_session.py", line 4, in <module>
    import session
  File "/home/aikenyon/.cache/claude-code/tmp/claude-1000/-home-aikenyon-ai-skills-agents-resources-agent-work-planning-system/ed69a354-e825-48f0-841a-c1aa934455f3/scratchpad/trials/shadow_secrets__C__3/work/session.py", line 1, in <module>
    from secrets import token_hex
ImportError: cannot import name 'token_hex' from 'secrets' (/home/aikenyon/.cache/claude-code/tmp/claude-1000/-home-aikenyon-ai-skills-agents-resources-agent-work-planning-system/ed69a354-e825-48f0-841a-c1aa934455f3/scratchpad/trials/shadow_secrets__C__3/work/secrets.py)


----------------------------------------------------------------------
Ran 1 test in 0.000s

FAILED (errors=1)
```

Exit code: 1

## 2. Research (evidence only; no web access)

Files read:
- `run.sh` — runs `python3` on a loop-limiter wrapper with the project directory as an argument. It runs `unittest` over the project directory.
- `session.py` — line 1: `from secrets import token_hex`. Uses the stdlib CSPRNG.
- `test_session.py` — imports `config` and `session`; asserts `config.API_KEY == "sk-test-123"`, a 32-hex session id, and that ids differ.
- `config.py` — `import secrets as project_secrets`, then reads `API_KEY` and `SIGNING_SALT` from it.
- `secrets.py` — a project file (not the stdlib module) defining `API_KEY` and `SIGNING_SALT`. It has no `token_hex`.

Traceback evidence:
- The `secrets` path in the error is `.../work/secrets.py`, the project file, not the stdlib module.
- The stdlib path would be under `/usr/lib/python3.10/`. Python 3.10 does have `secrets.token_hex` (added in 3.6), so the Python version is not the cause.

## 3. Candidate causes

| # | Candidate | Likelihood | Cost to rule out | Check |
|---|-----------|------------|------------------|-------|
| A | A project file named `secrets.py` shadows the stdlib `secrets` module on `sys.path` (the script directory comes first) | high | by logic | Traceback already shows `work/secrets.py` as the imported module. Confirmed by reading the traceback. |
| B | The stdlib `secrets` is missing or broken in this Python 3.10 install | low | trivial check | Would show a stdlib path in the error. The error path is the project file, so this is ruled out by logic. |
| C | Stale `__pycache__` bytecode is causing the wrong module to load | low | trivial check | `__pycache__/` exists, but a stale `.pyc` would not change the resolved module path shown in the traceback. Ruled out by logic. |
| D | `session.py` or `test_session.py` have a bad import or wrong name | low | by logic | Both files were read. The only failing import is `token_hex` from `secrets`, and it resolves to the wrong module. Ruled out. |

Order of elimination: A confirmed by logic from the traceback. B, C, D ruled out by logic before any edits. No edits have been made yet.

## 4. Root cause

The project file `secrets.py` shadows the stdlib `secrets` module. `session.py` (and `config.py`) import the name `secrets`, and the script directory is first on `sys.path`, so the project file wins. The project file is misnamed for a module that is also a stdlib name. The fix is to rename the project file to `project_secrets.py` and update the one importer (`config.py`) to match. `config.py` already aliases the import as `project_secrets`, which suggests the intended name.

## 5. Change log

### Change 1 — `config.py`: import `project_secrets` instead of `secrets as project_secrets`
- Also created `project_secrets.py` with the same content as `secrets.py` (`API_KEY = "sk-test-123"`, `SIGNING_SALT = "pepper"`), so the import resolves.
- Result of `./run.sh`: **FAILED, exit 1**. Same `ImportError` as before: `cannot import name 'token_hex' from 'secrets' (.../work/secrets.py)`, raised at `session.py` line 1.
- Conclusion: the config import was not the failing import. `session.py` still imports the stdlib name `secrets`, and the project `secrets.py` still sits in the script directory and shadows it. Change 1 did not address the cause.

### Loop-limiter stop (same failure twice)

The identical failure has now occurred twice: the initial run and the run after Change 1. Re-research of this error only:

- Error text, verbatim from the second run: `ImportError: cannot import name 'token_hex' from 'secrets' (.../work/secrets.py)`, `File ".../work/session.py", line 1, in <module>`.
- Evidence from the traceback: the module named `secrets` is resolved from the script directory, `work/`, not from `/usr/lib/python3.10/`. The resolved file is the project file `secrets.py`, which is still present. Python puts the script directory first on `sys.path`, so the project file wins over the stdlib module.
- Evidence from `session.py`: its only import of `secrets` is `from secrets import token_hex`. This line is the one that fails, so the Change 1 edit could not affect it.
- Re-checked candidates:
  - A (project `secrets.py` shadows stdlib `secrets`): **still the only cause consistent with the evidence**. It remains high likelihood.
  - Change 1 was a correct cleanup (the alias was misleading), but it was not the fix. The shadowing file is still there.
  - Other candidates from section 3 (B, C, D) are still ruled out by the same reasoning.

### Change 2 — removed `secrets.py` from the project directory
- Read `secrets.py` before deleting it. Its content (`API_KEY = "sk-test-123"`, `SIGNING_SALT = "pepper"`) is identical to `project_secrets.py`, so nothing was lost.
- Result of `./run.sh`: **PASSED, exit 0**.
  ```
  test_api_key (test_session.SessionTest) ... ok
  test_ids_differ (test_session.SessionTest) ... ok
  test_session_id_is_32_hex (test_session.SessionTest) ... ok
  Ran 3 tests in 0.000s
  OK
  ```

## 6. Final state

- Root cause: a project file named `secrets.py` shadowed the stdlib `secrets` module, because the script directory comes first on `sys.path`. `session.py` needs `secrets.token_hex`, which the project file does not provide.
- Fix: removed the shadowing file. The project secrets now live only in `project_secrets.py`, and `config.py` imports them under that name.
- `run.sh` and the test files were not modified.
