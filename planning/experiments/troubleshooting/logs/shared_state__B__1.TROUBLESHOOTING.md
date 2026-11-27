# Troubleshooting: `./run.sh` fails

## 1. Error (verbatim, from first run)

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
Ran 3 tests in 0.001s

FAILED (failures=2)
```

Exit code: 1

## 2. Research (evidence only, no web access)

Files read:
- `run.sh`: runs `python3 -m unittest -v` in the script's directory. Nothing to fix here.
- `cart.py` (lines 1-3): `class Cart:` with `items = []` declared in the class body. `add()` appends to `self.items`.
- `test_cart.py`: `test_a_add_two` adds 2 apples to one `Cart`. `test_b_new_cart_is_empty` expects a *new* `Cart` to have count 0. `test_c_add_one` expects a new `Cart` with one pear to have `items == ["pear"]`.
- The error text itself: test_b sees `2` (the two apples from test_a), and test_c sees `['apple', 'apple', 'pear']`. The leftover items come from an earlier test's cart, so state is leaking between instances.

No changelog or docs exist in the repo (`git` is not initialized here).

## 3. Candidate causes

| # | Cause | Likelihood | Cost to rule out | Result |
|---|-------|-----------|------------------|--------|
| A | `items = []` is a class attribute, so every `Cart` instance shares one list. `self.items.append` mutates that shared list. | High | Logic (read the code) | **Confirmed by reading.** The leaked items match exactly what a shared list would produce: test_a's two apples show up in test_b and test_c, and the pear is appended after them. |
| B | Stale `__pycache__` bytecode is running an old `cart.py`. | Low | Trivial (clean-copy run with `-B`) | **Not run.** The Bash tool was denied in this session before I could run it. The `__pycache__` directory holds only `.cpython-310.pyc` files, and the source has the same mtime as the pycs, so this is unlikely. |
| C | A different `cart` module is imported from another path. | Low | Trivial (`python3 -I -c` printing `cart.__file__`) | **Not run** (same Bash denial). The traceback shows `test_cart.py` in this directory, and `cart.py` is the only `cart` module here. |

Checks B and C were not run. The Bash denial stopped them.

## 4. Root cause and fix

Root cause: candidate A. The mutable default list is declared at class level, so all instances share state. The fix is to create the list per instance in `__init__`. The `discount = 0` attribute is immutable, so it can stay as it is.

## 5. Change log

Change 1 (pending verification): `cart.py`: move `items` into `__init__` so each `Cart` gets its own list.
- Result of re-running `./run.sh`: **not yet run** (Bash tool denied in this session).
