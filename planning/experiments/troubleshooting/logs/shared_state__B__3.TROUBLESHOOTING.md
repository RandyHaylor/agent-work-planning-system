# Troubleshooting: `./run.sh` fails

## Error (verbatim, run 1)

```
test_a_add_two (test_cart.CartTest) ... ok
test_b_new_cart_is_empty (test_cart.CartTest) ... FAIL
test_c_add_one (test_cart.CartTest) ... FAIL

FAIL: test_b_new_cart_is_empty (test_cart.CartTest)
  File ".../test_cart.py", line 14, in test_b_new_cart_is_empty
    self.assertEqual(c.count(), 0)
AssertionError: 2 != 0

FAIL: test_c_add_one (test_cart.CartTest)
  File ".../test_cart.py", line 19, in test_c_add_one
    self.assertEqual(c.items, ["pear"])
AssertionError: Lists differ: ['apple', 'apple', 'pear'] != ['pear']

Ran 3 tests in 0.000s
FAILED (failures=2)
EXIT: 1
```

## Research (local evidence only)

- `run.sh`: runs `python3 -m unittest -v` from the script's directory. Sets nothing else.
- `cart.py`: class `Cart` declares `items = []` at class level (line 2) and `add()` mutates it with `self.items.append(...)` (line 7). No `__init__`.
- `test_cart.py`: each test creates a fresh `Cart()` and expects an empty cart at start. `test_a` adds two apples; `test_b` then sees 2 items.
- The observed data (`['apple', 'apple', 'pear']`) shows the list survives across separate `Cart()` instances within one process.

## Candidate causes

| # | Cause | Likelihood | Cost to rule out |
|---|-------|-----------|------------------|
| 1 | `items = []` is a class-level mutable attribute, shared by all instances | high | logic (already read the code) |
| 2 | Stale `__pycache__/cart.cpython-*.pyc` serving old bytecode | low | trivial: check `cart.py` mtime vs pyc, and `python3 -c "import cart; print(cart.__file__)"` |
| 3 | A different `cart.py` on the import path shadows this one | low | trivial: the same `cart.__file__` check shows the loaded path |

Order: check 1 by logic (done), then 3 and 2 with the trivial check, since they are cheap.

## Checks

- Check 3 (import path): `python3 -c "import cart; print(cart.__file__)"` printed the local `cart.py`. **Ruled out.**
- Check 2 (stale bytecode): `cart.py` mtime 22:22:52; `cart.cpython-310.pyc` mtime 22:23:04 (newer, compiled from current source). **Ruled out.**
- Check 1 (class-level mutable list): confirmed by reading the code and the observed shared contents. **Remaining cause.**

## Fix 1 (root cause)

Move `items` into per-instance state via `__init__`, so each `Cart` gets its own list. Changed `cart.py` only; `run.sh` and tests are untouched.

Result: `./run.sh` → all 3 tests `ok`, `Ran 3 tests`, `OK`, EXIT 0. The fix resolved the failure on the first change, so no second failure occurred and no re-research was needed.
