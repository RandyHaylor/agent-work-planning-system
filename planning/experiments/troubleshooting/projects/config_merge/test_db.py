import unittest

import db
import settings


class DbTest(unittest.TestCase):
    def test_connection_string(self):
        cfg = settings.load()
        self.assertEqual(db.connection_string(cfg), "postgres://base/app?pool=20")

    def test_debug_from_local(self):
        self.assertTrue(settings.load()["debug"])


if __name__ == "__main__":
    unittest.main()
