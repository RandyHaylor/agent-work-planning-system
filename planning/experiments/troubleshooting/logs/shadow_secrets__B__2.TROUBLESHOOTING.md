# Troubleshooting: `./run.sh` fails

## 1. Error (verbatim, from first run of `./run.sh`)

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
  File "/home/aikenyon/.cache/claude-code/tmp/claude-1000/-home-aikenyon-ai-skills-agents-resources-agent-work-planning-system/ed69a354-e825-48f0-841a-c1aa934455f3/scratchpad/trials/shadow_secrets__B__2/work/test_session.py", line 4, in <module>
    import session
  File "/home/aikenyon/.cache/claude-code/tmp/claude-1000/-home-aikenyon-ai-skills-agents-resources-agent-work-planning-system/ed69a354-e825-48f0-841a-c1aa934455f3/scratchpad/trials/shadow_secrets__B__2/work/session.py", line 1, in <module>
    from secrets import token_hex
ImportError: cannot import name 'token_hex' from 'secrets' (/home/aikenyon/.cache/claude-code/tmp/claude-1000/-home-aikenyon-ai-skills-agents-resources-agent-work-planning-system/ed69a354-e825-48f0-841a-c1aa934455f3/scratchpad/trials/shadow_secrets__B__2/work/secrets.py)


----------------------------------------------------------------------
Ran 1 test in 0.000s

FAILED (errors=1)
```

Exit code: 1

## 2. Research (evidence only; no web access)

Files and docs read:
- The error text itself. The last line of the traceback names the resolved file: `.../work/secrets.py`, not the stdlib `secrets`. That is the key evidence.
- `session.py` line 1: `from secrets import token_hex`. This is the failing import.
- `secrets.py` (project file): defines `API_KEY` and `SIGNING_SALT`, no `token_hex`. It is a project settings module, not the stdlib module.
- `config.py` line 1: `import secrets as project_secrets`. It reads the project file through the same name, so it collides with the stdlib name too.
- `test_session.py`: imports `config` and `session`. It must not be edited.
- `run.sh`: `cd "$(dirname "$0")"` then `python3 -m unittest -v`. Python puts the script's directory first on `sys.path`, so local files shadow stdlib modules of the same name.
- Traceback frame at `unittest/loader.py` line 436/377 (Python 3.10): confirms the failure happens during module import, before any test runs.

Limitation: the shell was denied after the first run (permission mode "don't ask"), so I could not run `git log`, `ls __pycache__`, or re-run the command after each change. Findings below are from reading files and the traceback.

## 3. Candidate causes (cheapest to eliminate first)

| # | Candidate | Likelihood | Cost to rule out |
|---|-----------|-----------|------------------|
| A | Project file `secrets.py` shadows the stdlib `secrets` module (local directory first on `sys.path`) | high | by logic: the traceback's last line shows the resolved path is the local `secrets.py` |
| B | Python version lacks `secrets.token_hex` | low | by logic: `secrets` was added in Python 3.6 and `token_hex` has always been there; the interpreter is 3.10 |
| C | Stale `__pycache__` holding old bytecode | low | by logic: bytecode is keyed to source file names; a stale `.pyc` cannot change which file the name `secrets` resolves to. Not checked with a shell (denied) |
| D | `run.sh` runs from the wrong directory, so the wrong files are picked up | low | by logic: `run.sh` already does `cd "$(dirname "$0")"`, and the traceback paths are all in `work/` |

## 4. Check results

- A: **confirmed**. The traceback's path is `.../work/secrets.py`. `session.py` and `config.py` both import the name `secrets`, which the local file captures.
- B: **ruled out**. The stdlib import line in the traceback is `/usr/lib/python3.10/...`, a modern Python. `token_hex` is a standard function; the failure is the name resolving to the wrong module, not the function missing.
- C: **not checked** (shell denied). Judged unlikely by logic (see above).
- D: **ruled out**. Paths in the traceback are all under `work/`, and `run.sh` changes into its own directory.

## 5. Root cause

The project's settings module is named `secrets.py`, the same as a Python standard-library module. Because the script directory comes first on `sys.path`, `from secrets import token_hex` loads the project file instead of the stdlib. The fix is to rename the project module (for example to `project_secrets.py`) and update the one import in `config.py`.

## 6. Planned changes (one at a time)

1. Create `project_secrets.py` with the same contents as `secrets.py`.
2. Update `config.py` to `import project_secrets`.
3. Delete `secrets.py`. **Blocked**: deletion needs a shell and Bash is denied. Requires the user to run `rm secrets.py`, or to approve shell access.
4. Re-run `./run.sh` after each change and record the result here.

## 7. Change log and results

- Change 1 (done): created `project_secrets.py` with the same contents as `secrets.py`. Not yet run: shell denied.
- Change 2 (done): `config.py` line 1 changed from `import secrets as project_secrets` to `import project_secrets`. Not yet run: shell denied.
- Change 3 (NOT done): delete `secrets.py`. Until this is removed, `session.py`'s `from secrets import token_hex` still resolves to the local file and `./run.sh` will still fail with the same ImportError. **Action needed: run `rm secrets.py` in the `work/` directory, then run `./run.sh`.**

Expected result after change 3: `session.new_session_id()` and `config` import cleanly; the three tests in `test_session.py` should pass. This is unverified.
