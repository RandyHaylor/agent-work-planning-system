# TROUBLESHOOTING: `./run.sh` fails

## 1. Error (verbatim, first run of `./run.sh`, exit code 1)

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
  File "/home/aikenyon/.cache/claude-code/tmp/claude-1000/-home-aikenyon-ai-skills-agents-resources-agent-work-planning-system/ed69a354-e825-48f0-841a-c1aa934455f3/scratchpad/trials/shadow_secrets__B__1/work/test_session.py", line 4, in <module>
    import session
  File "/home/aikenyon/.cache/claude-code/tmp/claude-1000/-home-aikenyon-ai-skills-agents-resources-agent-work-planning-system/ed69a354-e825-48f0-841a-c1aa934455f3/scratchpad/trials/shadow_secrets__B__1/work/session.py", line 1, in <module>
    from secrets import token_hex
ImportError: cannot import name 'token_hex' from 'secrets' (/home/aikenyon/.cache/claude-code/tmp/claude-1000/-home-aikenyon-ai-skills-agents-resources-agent-work-planning-system/ed69a354-e825-48f0-841a-c1aa934455f3/scratchpad/trials/shadow_secrets__B__1/work/secrets.py)


----------------------------------------------------------------------
Ran 1 test in 0.000s

FAILED (errors=1)
```

## 2. Research (evidence only; no web access)

Files read as evidence:
- `run.sh`: runs `cd "$(dirname "$0")"` then `python3 -m unittest -v`. Running from the project directory means the project directory is first on `sys.path`.
- `session.py`: line 1 is `from secrets import token_hex`.
- `secrets.py`: a project file (not the stdlib) containing only `API_KEY` and `SIGNING_SALT`.
- `config.py`: `import secrets as project_secrets`, then reads `API_KEY` and `SIGNING_SALT` from it.
- `test_session.py`: imports `config` and `session`, and checks `token_hex`-based IDs and `config.API_KEY`.

What the error text says:
- The traceback path for `token_hex` lookup is `.../work/secrets.py`, not the stdlib `secrets.py`. So `from secrets import token_hex` resolved to the project file.
- The message is "cannot import name 'token_hex' from 'secrets'", which is the normal result when a module named `secrets` exists but lacks that name.
- Python's import system searches the script directory before the stdlib, so a project-level `secrets.py` shadows the stdlib `secrets` module.

No docs or changelog exist in the repo to consult.

## 3. Candidate causes

| # | Candidate | Likelihood | Cost to rule out | Order |
|---|-----------|------------|------------------|-------|
| A | Project file `secrets.py` shadows the stdlib `secrets` module (name collision on `sys.path[0]`) | High | By logic: the traceback path already points at `work/secrets.py` | 1 |
| B | Python 3.10 lacks `secrets.token_hex` (or the stdlib module is broken) | Low | Trivial: `token_hex` has existed since Python 3.6, and the Python in the traceback is 3.10 | 2 |
| C | `run.sh` runs the wrong interpreter or working directory, so the test module is found in the wrong place | Low | By logic: `run.sh` does `cd "$(dirname "$0")"`, and the traceback paths are the project directory | 3 |

## 4. Checks and results

- **Check A (by logic):** The traceback's `cannot import name ... from 'secrets' (.../work/secrets.py)` shows the stdlib module was never reached. Result: **supported**. Root cause is the shadowing file.
- **Check B (trivial, by logic):** The error is "cannot import name 'token_hex'", not "No module named" or a version error. The stdlib `secrets` module is what gets loaded here, and it is the project file. Result: **ruled out** as a cause, since the stdlib module is never consulted.
- **Check C (by logic):** The traceback paths all point into the project directory, which matches `run.sh`'s `cd`. Result: **ruled out**.

**Root cause:** The project file `secrets.py` shadows the stdlib `secrets` module. The file is named after a stdlib module, so `session.py`'s `from secrets import token_hex` loads it.

**Planned fix (one change at a time):** Rename the project file `secrets.py` to `project_secrets.py`, then point `config.py` at the new name. This fixes the root cause, not the symptom. Test and `run.sh` files stay unchanged.

## 5. Change log

### Change 1: rename `secrets.py` -> `project_secrets.py`
- Command: `mv secrets.py project_secrets.py`
- Result: file renamed. Not run on its own: `config.py` still did `import secrets as project_secrets`, which now resolves to the stdlib module and would fail with a missing `API_KEY`. (Deviation from one-change-at-a-time: the rename and the import edit in Change 2 were applied before the next run.)

### Change 2: `config.py` imports the renamed module
- Edit: `import secrets as project_secrets` -> `import project_secrets`
- Command: `./run.sh; echo "EXIT: $?"`
- Result:
```
test_api_key (test_session.SessionTest) ... ok
test_ids_differ (test_session.SessionTest) ... ok
test_session_id_is_32_hex (test_session.SessionTest) ... ok

----------------------------------------------------------------------
Ran 3 tests in 0.000s

OK
EXIT: 0
```

## 6. Outcome
- `./run.sh` passes (3 tests, exit 0).
- Files changed: `secrets.py` renamed to `project_secrets.py`; `config.py` import line updated.
- Not changed: `run.sh`, `test_session.py`, `session.py`.
- Verification: `session.py` was not edited; it now gets the stdlib `secrets.token_hex` because the project file no longer shadows it.
