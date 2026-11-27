# Troubleshooting: `./run.sh` fails

## 1. Error (verbatim, from the first run of `./run.sh`)

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
  File "/home/aikenyon/.cache/claude-code/tmp/claude-1000/-home-aikenyon-ai-skills-agents-resources-agent-work-planning-system/ed69a354-e825-48f0-841a-c1aa934455f3/scratchpad/trials/shadow_secrets__B__3/work/test_session.py", line 4, in <module>
    import session
  File "/home/aikenyon/.cache/claude-code/tmp/claude-1000/-home-aikenyon-ai-skills-agents-resources-agent-work-planning-system/ed69a354-e825-48f0-841a-c1aa934455f3/scratchpad/trials/shadow_secrets__B__3/work/session.py", line 1, in <module>
    from secrets import token_hex
ImportError: cannot import name 'token_hex' from 'secrets' (/home/aikenyon/.cache/claude-code/tmp/claude-1000/-home-aikenyon-ai-skills-agents-resources-agent-work-planning-system/ed69a354-e825-48f0-841a-c1aa934455f3/scratchpad/trials/shadow_secrets__B__3/work/secrets.py)


----------------------------------------------------------------------
Ran 1 test in 0.000s

FAILED (errors=1)
```

Exit code: 1

## 2. Research (evidence only; no web access)

Files and docs read:

- `run.sh`: runs `cd "$(dirname "$0")"` then `python3 -m unittest -v`. Working directory is the project, so it is first on `sys.path`.
- `session.py`: line 1 is `from secrets import token_hex`. This is the line named in the traceback.
- `secrets.py`: a project file containing `API_KEY` and `SIGNING_SALT`. The traceback shows `from 'secrets' (.../work/secrets.py)`, so Python resolved `secrets` to this file, not the stdlib module.
- `config.py`: line 1 is `import secrets as project_secrets`. It imports the project file under the name `secrets`, which is the same shadowing problem.
- `test_session.py`: imports `config` and `session`, and checks `new_session_id()` (32 hex chars, unique) and `config.API_KEY == "sk-test-123"`.
- `__pycache__/` (Glob listing): contains `secrets.cpython-310.pyc`, `session.cpython-310.pyc`, `config.cpython-310.pyc`, `test_session.cpython-310.pyc`. Interpreter is Python 3.10 (from the traceback path `/usr/lib/python3.10`).
- No TROUBLESHOOTING-related docs, changelog, or README exist in the project directory.

## 3. Candidate causes

| # | Candidate | Likelihood | Cost to rule out | Order |
|---|-----------|------------|------------------|-------|
| A | Project file `secrets.py` shadows the stdlib `secrets` module on `sys.path` (cwd is first) | High | Logic: the traceback already names `.../work/secrets.py` as the module that was loaded | 1 |
| B | Stale bytecode in `__pycache__/` (e.g. a `secrets` pyc left over from an older layout) | Low | Trivial: list `__pycache__` | 2 |
| C | Wrong Python interpreter / broken stdlib install (`/usr/lib/python3.10/secrets.py` missing `token_hex`) | Low | Costly: needs running Python and inspecting the stdlib install, which is blocked here | 3 |

## 4. Results of checks

- **A: CONFIRMED by logic.** The `ImportError` message gives the file path of the loaded module as `secrets.py` in the project directory. `secrets.py` is a project file with no `token_hex`, so `from secrets import token_hex` fails. `config.py` also imports this file under the name `secrets`, so the same shadowing affects it. This is the root cause.
- **B: Ruled out as the cause.** `__pycache__` only holds `.pyc` files for the same modules in the project. Stale bytecode would not change which file `import secrets` resolves to, because the `.py` source in the cwd is still found first. Stale pyc is not the cause; `__pycache__` can be cleared later as housekeeping.
- **C: Not checked.** The traceback path `/usr/lib/python3.10/unittest/...` shows a standard interpreter, and the failure is explained by A without needing C. Not pursued.

## 5. Planned fix (root cause, not a symptom)

Rename the project module so that it no longer shares the stdlib name:

1. `mv secrets.py project_secrets.py`
2. In `config.py`, change `import secrets as project_secrets` to `import project_secrets`.

`session.py` and `test_session.py` stay unchanged, so `from secrets import token_hex` resolves to the stdlib module again.

## 6. Change log

| Step | Change | Result of `./run.sh` |
|------|--------|----------------------|
| 0 | None (baseline run) | FAILED, exit 1, `ImportError: cannot import name 'token_hex' from 'secrets' (.../work/secrets.py)` |
| 1 | Not yet applied. Blocked: the shell tool was denied in this session (`don't ask` permission mode), so `mv` and re-running `./run.sh` could not be executed. | Not run |

Status: root cause identified; fix not yet applied; verification pending.
