# TROUBLESHOOTING: `./run.sh` fails

## 1. Error (run once, verbatim)

Command: `./run.sh` (run from the project directory)

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
  File "/home/aikenyon/.cache/claude-code/tmp/claude-1000/-home-aikenyon-ai-skills-agents-resources-agent-work-planning-system/ed69a354-e825-48f0-841a-c1aa934455f3/scratchpad/trials/shadow_secrets__C__1/work/test_session.py", line 4, in <module>
    import session
  File "/home/aikenyon/.cache/claude-code/tmp/claude-1000/-home-aikenyon-ai-skills-agents-resources-agent-work-planning-system/ed69a354-e825-48f0-841a-c1aa934455f3/scratchpad/trials/shadow_secrets__C__1/work/session.py", line 1, in <module>
    from secrets import token_hex
ImportError: cannot import name 'token_hex' from 'secrets' (/home/aikenyon/.cache/claude-code/tmp/claude-1000/-home-aikenyon-ai-skills-agents-resources-agent-work-planning-system/ed69a354-e825-48f0-841a-c1aa934455f3/scratchpad/trials/shadow_secrets__C__1/work/secrets.py)


----------------------------------------------------------------------
Ran 1 test in 0.000s

FAILED (errors=1)
```

Exit code: 1

## 2. Research (error text and the code it points at only)

Files and docs read as evidence:
- `run.sh`: runs `python3 -m unittest -v` from the script's own directory. Inside the project directory, that puts the project directory first on `sys.path`.
- `.real_run.sh`: the wrapper that `run.sh` execs through the loop limiter. Not part of the failure.
- `session.py` line 1: `from secrets import token_hex`. This is the line the traceback points at.
- `secrets.py` (project root): a 3-line file that defines `API_KEY` and `SIGNING_SALT`. It is named `secrets.py`, the same name as the Python standard library module `secrets`.
- `config.py` line 1: `import secrets as project_secrets`. It reads the project file under the stdlib module's name.
- `test_session.py`: imports `config` and `session`. Not edited.
- Traceback path: `from 'secrets' (/…/work/secrets.py)`. The name `secrets` resolved to the project file, not to the stdlib. The error text itself shows the shadowing.
- Glob `/usr/lib/python3.10/secrets.py`: exists, so the stdlib module is installed.
- Glob `__pycache__/`: contains `secrets.cpython-310.pyc`, a cached copy of the project file under the stdlib name.
- Grep `secrets` in the project: only `config.py`, `session.py`, and `run.sh` (the path only) reference the name.

## 3. Candidate causes

| # | Candidate | Likelihood | Cost to rule out | Order |
|---|-----------|-----------|------------------|-------|
| A | The project file `secrets.py` shadows the stdlib `secrets` module, because the project directory is first on `sys.path`. | High | By logic (the traceback path already shows `secrets` resolving to `/work/secrets.py`) | 1 |
| B | The stdlib `secrets` module is missing or broken in this Python 3.10 install. | Low | Trivial (Glob for `/usr/lib/python3.10/secrets.py`) | 2 |
| C | A `PYTHONPATH` entry or `.pth` file injects another `secrets` module ahead of the stdlib. | Low | Trivial (Grep of the repo's run scripts for `PYTHONPATH`; no environment access) | 3 |
| D | A stale `__pycache__` entry is being loaded instead of the source. | Low | Trivial (Glob of `__pycache__`) | 4 |

## 4. Check results

- **A (by logic):** Confirmed as the root cause. The traceback shows `from 'secrets' (…/work/secrets.py)`. `session.py` line 1 is the only place that imports `token_hex`, and `token_hex` exists only in the stdlib module.
- **B (Glob `/usr/lib/python3.10/secrets.py`):** Result: file exists. Ruled out.
- **C (Grep for `PYTHONPATH` in the repo):** Not run in this check. Environment access was denied (see the Bash note below). The error path already shows the project file winning, so C is not needed to explain the failure. Left unverified, not ruled out.
- **D (Glob `__pycache__`):** Result: contains `secrets.cpython-310.pyc`, which is the compiled project file under the shadowed name. It is a side effect of A, not a separate cause. Ruled out as a cause.

Note: a Bash call used to read the files and `git status` was denied by the permission mode. Reads were done with the Read/Glob/Grep tools instead. This means `git status` and a second run of `./run.sh` could not be done under the current permissions at the time of this record.

## 5. Root cause

The project's `secrets.py` has the same module name as the stdlib `secrets`. Because the project directory is first on `sys.path` when the tests run, `session.py`'s `from secrets import token_hex` loads the project file instead of the stdlib module. The project file has no `token_hex`, so the import fails.

The fix is to rename the project module so it no longer shadows the stdlib name, and update the one import that refers to it (`config.py`). `run.sh` and the test files are not touched.

## 6. Planned change (one at a time)

1. Rename `secrets.py` to `project_secrets.py`. Re-run `./run.sh` and record the result below.
2. Update `config.py` from `import secrets as project_secrets` to `import project_secrets`. Re-run `./run.sh` and record the result below.

## 7. Change log

- **Attempt 1 (rename `secrets.py` -> `project_secrets.py`):** NOT PERFORMED. The rename requires deleting or moving `secrets.py`. The available file tools (Write/Edit) cannot delete or move files, and the Bash call needed to do it was denied by the permission mode. No code was changed. `run.sh` and the test files were not touched.
- **Result after attempt 1:** No re-run needed, since no change was made. The last run is the one in section 1, still failing with the same `ImportError`.
- **Pending:** Step 1 above must be done before step 2 can help. Step 2 alone (editing `config.py`) would not fix the failure, because `session.py`'s `from secrets import token_hex` would still resolve to the local `secrets.py`.

Exact commands the user can run to finish the fix:

```
cd <project dir>
mv secrets.py project_secrets.py
sed -i 's/^import secrets as project_secrets$/import project_secrets/' config.py
rm -rf __pycache__
./run.sh
```
