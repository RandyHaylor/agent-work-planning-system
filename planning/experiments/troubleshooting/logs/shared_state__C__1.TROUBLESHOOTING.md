# TROUBLESHOOTING: `./run.sh` fails

## 1. Error (verbatim, first run of `./run.sh`, exit status 1)

```
test_a_add_two (test_cart.CartTest) ... ok
test_b_new_cart_is_empty (test_cart.CartTest) ... FAIL
test_c_add_one (test_cart.CartTest) ... FAIL

======================================================================
FAIL: test_b_new_cart_is_empty (test_cart.CartTest)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/home/aikenyon/.cache/claude-code/tmp/claude-1000/-home-aikenyon-ai-skills-agents-resources-agent-work-planning-system/ed69a354-e825-48f0-841a-c1aa934455f3/scratchpad/trials/shared_state__C__1/work/test_cart.py", line 14, in test_b_new_cart_is_empty
    self.assertEqual(c.count(), 0)
AssertionError: 2 != 0

======================================================================
FAIL: test_c_add_one (test_cart.CartTest)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/home/aikenyon/.cache/claude-code/tmp/claude-1000/-home-aikenyon-ai-skills-agents-resources-agent-work-planning-system/ed69a354-e825-48f0-841a-c1aa934455f3/scratchpad/trials/shared_state__C__1/work/test_cart.py", line 19, in test_c_add_one
    self.assertEqual(c.items, ["pear"])
AssertionError: Lists differ: ['apple', 'apple', 'pear'] != ['pear']

First differing element 0:
'apple'
'pear'

First list contains 2 additional elements.
First extra element 1:
'apple'

- ['apple', 'apple', 'pear']
+ ['pear']

----------------------------------------------------------------------
Ran 3 tests in 0.000s

FAILED (failures=2)
```

## 2. Research (error text and repo files only; no web access)

Files read as evidence:
- `run.sh` — wrapper that execs `loopguard.py` around the test run. Its only job is the loop limiter; it does not affect test results. (Read-only; not modified.)
- `.real_run.sh` — the inner script: `cd` to its directory, then `python3 -m unittest -v`. Confirms the tests run in the work directory with `cart` imported from there.
- `test_cart.py` — tests use `Cart()` fresh in each test. `test_a` adds 2 "apple"; `test_b` expects a *new* cart to have count 0; `test_c` expects a *new* cart with `add("pear")` to have items `["pear"]`.
- `cart.py` — `class Cart:` declares `items = []` at class level (line 2). `add()` calls `self.items.append(...)`, which mutates the single list object owned by the class, not a per-instance list.
- Traceback paths point to `test_cart.py` line 14 and 19 in the work directory, so the module under test is the local `cart.py`.
- unittest runs tests in alphabetical order (a, b, c), which matches the output order.

The error text itself says: a new `Cart` reports count 2 after `test_a` added two items, and `items` contains leftover "apple" entries. That is state leaking between instances.

## 3. Candidate causes

| # | Candidate cause | Likelihood | Cost to rule out | Check |
|---|---|---|---|---|
| A | Mutable class attribute `items = []` is shared by all `Cart` instances, so `test_a`'s items leak into later tests. | high | by logic | Read `cart.py` line 2 and the error (leftover "apple" in a new cart). |
| B | Test-order dependence / test pollution: tests only fail because `test_a` runs first. | medium | trivial | Same evidence as A; the root is still shared state, so B is a symptom of A. Confirmed by logic. |
| C | Stale `__pycache__` bytecode is serving an old `cart.py`. | low | trivial | `__pycache__` exists in the directory. Tracebacks show current source lines (`self.items.append`); a stale cache would not produce a logic error like this. Eliminated by logic. |
| D | A different `cart` module is imported (shadowing on `sys.path`). | low | trivial | Traceback shows `test_cart.py` in the work dir; `cart.py` is the only `cart` module in the listing. Eliminated by listing. |

Order of checks: A (by logic), then C and D (trivial), then B (by logic, as a consequence of A).

## 4. Results of checks

- A: **Confirmed.** `cart.py:2` is `items = []` at class level, and `add` appends to `self.items`. Because `self.items` is not assigned on the instance, it resolves to the one shared class list. The observed failure (count 2 on a new cart; `['apple', 'apple', 'pear']`) matches exactly.
- B: Consistent with A. Fixing A removes the dependence on order.
- C: Eliminated. Tracebacks reflect current source. Not run; ruled out by reasoning from the error text.
- D: Eliminated. Only one `cart.py` exists in the work directory and the traceback points there.

## 5. Root cause

`Cart.items` is a class-level mutable default. Each instance must own its own list, created in `__init__`.

## 6. Change log

| Step | Change | Command run | Result |
|---|---|---|---|
| 0 | None (baseline) | `./run.sh` | FAILED (failures=2), exit 1 |
| 1 | `cart.py`: replace class attribute `items = []` with per-instance `self.items = []` in `__init__` | — | Pending: `./run.sh` could not be executed afterward (see Notes) |

## Notes

- After the baseline run, the Bash tool was denied by the session's permission mode ("don't ask" mode), so `./run.sh` could not be re-run to verify step 1. The fix below is verified by reading the code only.
- `run.sh`, `.real_run.sh`, `test_cart.py`, and the `guard/` loop limiter were not modified.
