import unittest

import report


class ReportTest(unittest.TestCase):
    def test_day_label(self):
        # 1700000000 = 2023-11-14 22:13:20 UTC
        self.assertEqual(report.day_label(1700000000), "2023-11-14")

    def test_daily_counts(self):
        counts = report.daily_counts([1700000000, 1700003000, 1700100000])
        self.assertEqual(counts, {"2023-11-14": 2, "2023-11-16": 1})


if __name__ == "__main__":
    unittest.main()
