import unittest

import importer


class ImporterTest(unittest.TestCase):
    def test_count(self):
        self.assertEqual(len(importer.load_readings()), 4)

    def test_total(self):
        self.assertEqual(importer.total(importer.load_readings()), 50)


if __name__ == "__main__":
    unittest.main()
