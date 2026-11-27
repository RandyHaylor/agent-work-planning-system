# Troubleshooting: `./run.sh` fails

## 1. Error (verbatim, from first run of `./run.sh`)

```
test_a_add_two (test_cart.CartTest) ... ok
test_b_new_cart_is_empty (test_cart.CartTest) ... FAIL
test_c_add_one (test_cart.CartTest) ... FAIL

======================================================================
FAIL: test_b_new_cart_is_empty (test_cart.CartTest)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "test_cart.py", line 14, in test_b_new_cart_is_empty
    self.assertEqual(c.count(), 0)
AssertionError: 2 != 0

======================================================================
FAIL: test_c_add_one (test_cart.CartTest)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "test_cart.py", line 19, in test_c_add_one
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

(Traceback paths shortened to relative names; the original paths were absolute.)

## 2. Research (evidence only; no web access)

Files read:
- `run.sh`: `cd`s to its own directory, then runs `python3 -m unittest -v`. Does not set any state.
- `cart.py` lines 1-10: `class Cart` declares `items = []` at class level (line 2), and `add()` calls `self.items.append(sku)`. Because `self.items` is not assigned in `__init__`, `append` mutates the one list object owned by the class.
- `test_cart.py`: each test creates a fresh `Cart()` and expects an empty cart in `test_b`. `test_a` runs first (alphabetical order) and appends two `"apple"` entries, which `test_b` then sees.
- The error text itself: `2 != 0` in `test_b` and `['apple', 'apple', 'pear']` in `test_c` are exactly the contents left by `test_a` and `test_b`/`test_a` in the shared list. This matches the class-level mutable default.
- No git repo here (`git status` returns "not a git repository"), so no changelog/history is available.

## 3. Candidate causes

| # | Cause | Likelihood | Cost to rule out |
|---|-------|-----------|------------------|
| A | Mutable class attribute `items = []` shared across all `Cart` instances (state leaks between instances) | High | Logic: the error values match exactly what `test_a` would leave in a shared list. Trivial check: confirm `Cart().items is Cart().items` in Python. |
| B | Stale bytecode in `__pycache__` running an old version of `cart.py` | Low | Trivial: run with `python3 -B` / inspect `__pycache__` timestamps, or compile fresh. |
| C | Test ordering / pollution from another test file or a test-runner setting | Low | Costly-ish: only one test file exists (`test_cart.py`); run each test in isolation to check. |

Checks run in order of cost: A (logic + trivial), then B, then C.

## 4. Check results

- **Check A (shared mutable class attribute): supported.** Confirmed by reading `cart.py` and by the error values. The `python3 -c "... Cart().items is Cart().items"` identity check was attempted but the Bash tool was denied by permission mode at that point, so the identity check itself was not run. The fix below was verified by the test run instead.
- **Check B (stale `__pycache__`): ruled out by logic.** The cache contains `cart.cpython-310.pyc` and `test_cart.cpython-310.pyc`. CPython validates each `.pyc` against its source's mtime and size and recompiles on mismatch, so a stale cache cannot produce this failure. Not executed directly (Bash denied at that point).
- **Check C (test-order pollution from another source): ruled out.** Only `test_cart.py` exists in the directory (Glob), and `test_a` leaving two `"apple"` entries in `test_b`'s cart is fully explained by the shared list. Per-test isolation runs were not executed (Bash denied).

## 5. Fix (one change)

`cart.py`: moved `items` from a class attribute (`items = []`) to an instance attribute set in `__init__` (`self.items = []`). Each `Cart` now owns its own list. `discount` was left unchanged (unrelated, and it is immutable so it is safe as a class attribute).

## 6. Verification after the change

`./run.sh` (after the fix):
```
test_a_add_two (test_cart.CartTest) ... ok
test_b_new_cart_is_empty (test_cart.CartTest) ... ok
test_c_add_one (test_cart.CartTest) ... ok

----------------------------------------------------------------------
Ran 3 tests in 0.000s

OK
```
Exit code: 0.

Result: the original failure is resolved. Run-in-isolation and identity checks were not executed, as noted in section 4.
