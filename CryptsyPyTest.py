import unittest

from datetime import datetime, timedelta
from CryptsyPy import toCryptsyServerTime, fromCryptsyServerTime, CRYPTSY_HOURS_DIFFERENCE


class TestSequenceFunctions(unittest.TestCase):
    # def setUp(self):

    def test_toCryptsyServerTime(self):
        now = datetime.now()
        cryptsy_time = toCryptsyServerTime(now)
        self.assertEqual(cryptsy_time, now - timedelta(hours=CRYPTSY_HOURS_DIFFERENCE))

    def test_fromCryptsyServerTime(self):
        now = datetime.now()
        cryptsy_time = fromCryptsyServerTime(now)
        self.assertEqual(cryptsy_time, now + timedelta(hours=CRYPTSY_HOURS_DIFFERENCE))


if __name__ == '__main__':
    unittest.main()