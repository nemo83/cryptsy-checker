import unittest
import LinearRegressionTradingBot


class TestSequenceFunctions(unittest.TestCase):
    # def setUp(self):

    def test_basicNormalization(self):
        normalizedTimes, normalizedPrices = LinearRegressionTradingBot.getNormalizedTimesAndPrices([
            ("2014-07-01 12:00:00", "0.00000000"),
            ("2014-07-01 12:00:01", "0.00000001"),
            ("2014-07-01 12:00:02", "0.00000002"),

        ])
        self.assertEqual(normalizedTimes, [0, 0.5, 1])
        self.assertEqual(normalizedPrices, [0, 0.5, 1])

    def test_normalizationFirstAndLastSame(self):
        normalizedPrices, normalizedTimes = LinearRegressionTradingBot.getNormalizedTimesAndPrices([
            ("2014-07-01 12:00:00", "0.00000000"),
            ("2014-07-01 12:00:01", "0.00000001"),
            ("2014-07-01 12:00:02", "0.00000002"),
            ("2014-07-01 12:00:04", "0.00000000")
        ])

        self.assertEqual(normalizedTimes, [0, 0.25, 0.5, 1])
        self.assertEqual(normalizedPrices, [0, 0.5, 1, 0])

    def test_normalizationAllZeroes(self):
        normalizedPrices, normalizedTimes = LinearRegressionTradingBot.getNormalizedTimesAndPrices([
            ("2014-07-01 12:00:00", "0.00000000"),
            ("2014-07-01 12:00:00", "0.00000000"),
            ("2014-07-01 12:00:00", "0.00000000"),
            ("2014-07-01 12:00:01", "0.00000000"),
            ("2014-07-01 12:00:02", "0.00000000"),
            ("2014-07-01 12:00:04", "0.00000000")
        ])

        self.assertEqual(normalizedTimes, [0, 0, 0, 0.25, 0.5, 1])
        self.assertEqual(normalizedPrices, [0, 0, 0, 0, 0, 0])


if __name__ == '__main__':
    unittest.main()