import unittest
from datetime import timedelta

from CryptsyMongo import CryptsyMongo


class TestSequenceFunctions(unittest.TestCase):
    def setUp(self):
        self.mongo_client = CryptsyMongo()

    def test_simple(self):
        self.mongo_client.truncate_market_trend_collection()
        market_trend = self.mongo_client.calculateMarketTrend(market_name='LTC/BTC', market_id=3)
        self.assertIsNotNone(market_trend)

    def test_recent(self):
        self.mongo_client.truncate_market_trend_collection()
        num_market_trend = self.mongo_client.market_trend_collection.find().count()
        self.assertEqual(num_market_trend, 0)

        market_trend_1 = self.mongo_client.getRecentMarketTrend(market_name='LTC/BTC', market_id=3)
        num_market_trend = self.mongo_client.market_trend_collection.find().count()
        self.assertEqual(num_market_trend, 1)
        self.assertIsNotNone(market_trend_1)

        market_trend_2 = self.mongo_client.getRecentMarketTrend(market_name='LTC/BTC', market_id=3)
        num_market_trend = self.mongo_client.market_trend_collection.find().count()
        self.assertEqual(num_market_trend, 1)

        self.assertEqual(market_trend_1, market_trend_2)

    def test_recent(self):
        self.mongo_client.getRecentMarketTrend(market_name='LTC/BTC', market_id=3, timedelta=timedelta(minutes=1))
        self.mongo_client.getRecentMarketTrend(market_name='DOGE/BTC', market_id=132, timedelta=timedelta(minutes=1))
        self.mongo_client.getRecentMarketTrend(market_name='TEK/BTC', market_id=114, timedelta=timedelta(minutes=1))


if __name__ == '__main__':
    unittest.main()