import unittest

import numpy

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

    def test_calculateQuantity(self):
        amountToInvest = 0.001
        fee = 0.0025
        buyPrice = 0.00000001

        expectedQuantity = 99750

        self.assertEqual(int(LinearRegressionTradingBot.calculateQuantity(amountToInvest, fee, buyPrice)),
                         expectedQuantity)

    def test_poly(self):
        x = [0, 0.5, 1]
        y = [0, 0.5, 1]

        self.assertEqual(numpy.polyfit(x, y), [1, 0])

    def test_estimateValue(self):
        x = [0, 0.5, 1]
        y = [0, 0.5, 1]

        self.assertEqual(
            LinearRegressionTradingBot.estimateValue(3, m=1, n=0, minX=0, scalingFactorX=2, minY=0, scalingFactorY=2),
            3)


if __name__ == '__main__':
    unittest.main()