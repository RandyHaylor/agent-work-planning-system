import unittest

from cart import Cart


class CartTest(unittest.TestCase):
    def test_a_add_two(self):
        c = Cart()
        c.add("apple", qty=2)
        self.assertEqual(c.count(), 2)

    def test_b_new_cart_is_empty(self):
        c = Cart()
        self.assertEqual(c.count(), 0)

    def test_c_add_one(self):
        c = Cart()
        c.add("pear")
        self.assertEqual(c.items, ["pear"])


if __name__ == "__main__":
    unittest.main()
