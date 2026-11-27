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
  File "/home/aikenyon/.cache/claude-code/tmp/claude-1000/-home-aikenyon-ai-skills-agents-resources-agent-work-planning-system/ed69a354-e825-48f0-841a-c1aa934455f3/scratchpad/trials/shadow_secrets__C__2/work/test_session.py", line 4, in <module>
    import session
  File "/home/aikenyon/.cache/claude-code/tmp/claude-1000/-home-aikenyon-ai-skills-agents-resources-agent-work-planning-system/ed69a354-e825-48f0-841a-c1aa934455f3/scratchpad/trials/shadow_secrets__C__2/work/session.py", line 1, in <module>
    from secrets import token_hex
ImportError: cannot import name 'token_hex' from 'secrets' (/home/aikenyon/.cache/claude-code/tmp/claude-1000/-home-aikenyon-ai-skills-agents-resources-agent-work-planning-system/ed69a354-e825-48f0-841a-c1aa934455f3/scratchpad/trials/shadow_secrets__C__2/work/secrets.py)


----------------------------------------------------------------------
Ran 1 test in 0.000s

FAILED (errors=1)
EXIT=1
```

## 2. Research (error text and the code it points at only)

Files and docs I looked at:
- `run.sh` — wrapper; `exec`s a loop guard (`guard/loopguard.py`) that runs `python3 -m unittest -v` in the project dir. Not edited.
- `.real_run.sh` — same wrapper target, passes state file to the loop guard. Not edited.
- `session.py` — line 1 is `from secrets import token_hex`. This is the line named in the traceback.
- `secrets.py` — project file, not a stdlib file. Contains `API_KEY` and `SIGNING_SALT`. Its path is the one the traceback reports as the module that was loaded for `secrets`.
- `config.py` — does `import secrets as project_secrets` to read `secrets.py`.
- `test_session.py` — imports `config` and `session`. Not edited.
- Python 3.10 `unittest/loader.py` frames in the traceback (standard library, no changes needed there).

Key evidence: the traceback's last frame reports `(.../work/secrets.py)` as the origin of the `secrets` module. The working directory is first on `sys.path` when running `python3 -m unittest`, so a project-local `secrets.py` shadows the stdlib `secrets` module.

## 3. Candidate causes

| # | Candidate | Likelihood | Cost to rule out | Check |
|---|-----------|-----------|------------------|-------|
| A | Project file `secrets.py` shadows stdlib `secrets` (cwd is first on `sys.path`) | High | Logic | Traceback reports the origin as `work/secrets.py`, not the stdlib path. |
| B | Stdlib `secrets` on this Python lacks `token_hex` (broken or non-standard Python install) | Low | Trivial | Run `python3 -I -c "import secrets; print(secrets.__file__, secrets.token_hex)"` from outside the project dir. |
| C | `test_session` module failure is a separate problem (not the `secrets` import) | Low | Logic | The traceback shows the failure at `session.py` line 1, before the test code runs. |
| D | Stale `__pycache__` contains an old compiled module | Low | Logic | Traceback references the `.py` source path, and Python recompiles when the source is newer than the `.pyc`. |

Checks run in order of cost: A (logic), C (logic), D (logic), B (trivial command). Results are recorded below.

## 4. Check results

- **A — confirmed by logic.** The traceback origin is `.../work/secrets.py`, and `secrets.py` is a project file that lacks `token_hex`. The project directory shadows the stdlib module. Root cause.
- **C — ruled out by logic.** The failure happens at `session.py` line 1 during import, before any test code runs.
- **D — ruled out by logic.** The traceback reports the `.py` source path, so compiled cache content is not the cause.
- **B — ruled out.** Ran `python3 -I -c "import secrets; ..."` from outside the project dir. Result: `/usr/lib/python3.10/secrets.py True` — stdlib `secrets` exists and has `token_hex`. The Python install is fine.

## 5. Fix (root cause, not symptom)

Root cause: a project module named `secrets` shadows the Python standard library module `secrets`. The fix is to rename the project module so its name no longer collides with the stdlib. `config.py` is the only importer of it, so the rename needs an update there. `run.sh` and the test files stay unchanged.

Planned change (one step at a time, run `./run.sh` after each):
1. Rename `secrets.py` to `project_secrets.py`.
2. Update `config.py` to `import project_secrets`.

## 6. Run log

- Run 1 (baseline): FAILED, ImportError as quoted in section 1. Exit 1.
- Change 1: renamed `secrets.py` -> `project_secrets.py`.
- Run 2: FAILED, different error (not identical to run 1):
  ```
  File ".../work/config.py", line 3, in <module>
      API_KEY = project_secrets.API_KEY
  AttributeError: module 'secrets' has no attribute 'API_KEY'
  ```
  Cause: `config.py` still does `import secrets as project_secrets`, which now resolves to the stdlib module. Expected follow-on from change 1. Exit 1.
- Change 2: `config.py` changed from `import secrets as project_secrets` to `import project_secrets`.
- Run 3: PASSED. `Ran 3 tests ... OK`, exit 0.

## 7. Result

`./run.sh` passes. Root cause was the project file `secrets.py` shadowing the stdlib `secrets` module. Fixed by renaming it to `project_secrets.py` and updating the single import in `config.py`. `run.sh`, `session.py`, and the test files were not edited.
