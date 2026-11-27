# Troubleshooting: `./run.sh` failing

## Error (verbatim, first run)

```
test_a_add_two (test_cart.CartTest) ... ok
test_b_new_cart_is_empty (test_cart.CartTest) ... FAIL
test_c_add_one (test_cart.CartTest) ... FAIL

FAIL: test_b_new_cart_is_empty (test_cart.CartTest)
  File ".../work/test_cart.py", line 14, in test_b_new_cart_is_empty
    self.assertEqual(c.count(), 0)
AssertionError: 2 != 0

FAIL: test_c_add_one (test_cart.CartTest)
  File ".../work/test_cart.py", line 19, in test_c_add_one
    self.assertEqual(c.items, ["pear"])
AssertionError: Lists differ: ['apple', 'apple', 'pear'] != ['pear']

FAILED (failures=2)
```

## Research (files read as evidence; no web access)

- `run.sh`: wrapper that runs `loopguard.py` on the project dir. It only invokes `.real_run.sh` indirectly; the failure is in the unittest output itself.
- `.real_run.sh`: `cd`s to its dir and runs `python3 -m unittest -v`.
- `test_cart.py`: three tests. `test_a` adds 2 apples to a new `Cart()`, `test_b` expects a new `Cart()` to be empty, `test_c` adds one pear to a new `Cart()` and expects `items == ["pear"]`.
- `cart.py`: `Cart` defines `items = []` and `discount = 0` at **class level**. `add()` appends to `self.items`, which resolves to the single shared class-level list.
- `guard/state.json`: one recorded failure with the same signature (count 1). The guard stops after two identical failures, so the next identical failure triggers STOP.
- Error text points at the shared-list symptom: `test_b` sees the apples added by `test_a`.

## Candidate causes

| # | Candidate | Likelihood | Cost to rule out |
|---|-----------|------------|------------------|
| 1 | `items = []` is a class attribute, so all `Cart` instances share one list (state leaks between tests) | high | logic (read code) + trivial check |
| 2 | Stale `__pycache__/cart.cpython-310.pyc` serving old code | low | trivial check (run with bytecode disabled) |
| 3 | Another `cart` module shadows `work/cart.py` on `sys.path` | low | trivial check (print `cart.__file__`) |

## Checks (ordered cheapest first)

1. **Shared list identity (candidate 1)** — `python3 -B -c` creating two `Cart()` objects.
   - Result: `a.items is b.items: True`. Adding `'x'` to `a` made `b.count()` return `1`.
   - **Confirmed.** Candidate 1 is the cause.
2. **Module resolution (candidate 3)** — `import cart; cart.__file__`.
   - Result: `/.../work/cart.py`. Not shadowed.
   - **Ruled out.**
3. **Stale bytecode (candidate 2)** — ran unittest with `PYTHONDONTWRITEBYTECODE=1 python3 -B`, which ignores `__pycache__`.
   - Result: `Ran 3 tests ... FAILED (failures=2)`, same failures.
   - **Ruled out.**

## Fix plan

Root cause: mutable per-instance state declared as a class attribute. Fix in `cart.py` by initializing `items` in `__init__`, so each `Cart` gets its own list. Change one thing at a time and rerun after each change.

## Change log

### Change 1: move `items` into `__init__` (`cart.py`)
- Edit: `items = []` at class level → `self.items = []` in `__init__`.
- Result of `./run.sh`: (recorded below)
