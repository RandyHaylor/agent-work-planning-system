# Troubleshooting: `./run.sh` fails

## Error (verbatim from first run of `./run.sh`, exit=1)

```
test_a_add_two (test_cart.CartTest) ... ok
test_b_new_cart_is_empty (test_cart.CartTest) ... FAIL
test_c_add_one (test_cart.CartTest) ... FAIL

======================================================================
FAIL: test_b_new_cart_is_empty (test_cart.CartTest)
----------------------------------------------------------------------
Traceback (most recent call last):
  File ".../work/test_cart.py", line 14, in test_b_new_cart_is_empty
    self.assertEqual(c.count(), 0)
AssertionError: 2 != 0

======================================================================
FAIL: test_c_add_one (test_cart.CartTest)
----------------------------------------------------------------------
Traceback (most recent call last):
  File ".../work/test_cart.py", line 19, in test_c_add_one
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

Observed pattern: a brand-new `Cart()` already contains the two `apple` entries added by `test_a_add_two`. State from one instance is visible in another.

## Research (evidence only; no web access)

Files and docs read for this error:
- `run.sh`: wrapper that runs `python3 -m unittest -v` in its own directory, via `.real_run.sh`-style loop limiter (`guard/loopguard.py`). Not edited.
- `.real_run.sh`: the inner runner (`cd` to script dir, `python3 -m unittest -v 2>&1`).
- `test_cart.py`: three tests. Test b expects `Cart().count() == 0`. Test c expects `Cart().items == ["pear"]` after one add.
- `cart.py`: defines `class Cart` with `items = []` at class scope (line 2), `discount = 0` (line 3), `add()` appends to `self.items` (line 7), `count()` returns `len(self.items)`.
- The repo has no README or changelog; there are no docs to consult. The run output is the only other evidence.

## Candidate causes

| # | Candidate | Likelihood | Cost to rule out |
|---|-----------|------------|------------------|
| 1 | `items = []` is a class attribute shared by all instances, so `self.items.append` mutates one list for every `Cart`. | High | Logic (reading `cart.py`) |
| 2 | Test ordering / leftover state between tests (unittest runs tests alphabetically; `test_a` runs first). | Medium | Trivial check (run one test in isolation) |
| 3 | Stale `__pycache__` holding an old `cart.py` bytecode. | Low | Trivial check (remove cache, rerun) |
| 4 | `run.sh` or the loop limiter altering the test run (e.g. running tests twice). | Low | Logic (reading `run.sh`, `.real_run.sh`); the output shows each test only once, so this is unlikely |

Check order: cheapest first. 1 and 4 by logic. 3 and 2 by trivial checks if 1 does not fully explain the failure.

## Checks

### Check 1 (logic): is `items` shared across instances?
- Result: **Confirmed by reading.** `items` is declared at class level in `cart.py:2`. `self.items.append(...)` does not create an instance attribute; it mutates the class-level list. `test_a` appends two `apple`s to that list, and `test_b` (a fresh `Cart`) sees length 2. Test c then sees `['apple', 'apple', 'pear']`. This matches the output exactly.

### Check 4 (logic): does the runner do something unusual?
- Result: **Ruled out.** `.real_run.sh` runs `python3 -m unittest -v` once. Each test appears once in the output, and the failing values match the shared-list explanation.

Candidates 2 and 3 are not checked yet. Check 1 explains every observed value, so they are not needed unless the fix fails.

## Root cause

Mutable state is defined as a class attribute (`items = []` in `cart.py`) instead of per-instance state set in `__init__`. Every `Cart` instance shares one list. That is the root cause, not the test values.

## Fix plan (one change at a time)

1. Change `cart.py` only: move `items` into `__init__` as `self.items = []` (per instance). Run `./run.sh` and record the result below.

## Change log

### Change 1: `cart.py` — initialize `items` per instance
- Edit: removed `items = []` from class body; added `__init__` that sets `self.items = []`.
- Result: `./run.sh` exit 0. All 3 tests pass (`Ran 3 tests ... OK`). Candidates 2 and 3 were not needed.
