import unittest
from CryptsyMongo import CryptsyMongo


class TestSequenceFunctions(unittest.TestCase):
    def setUp(self):
        self.mongo_client = CryptsyMongo()

    def test_simple(self):
        self.mongo_client.truncate_market_trend_collection()
        market_trend = self.mongo_client.calculateMarketTrend(market_name='LTC/BTC', market_id=3)
        self.assertIsNotNone(market_trend)

    # def test_recent(self):
    #     cryptsyMongo = CryptsyMongo()
    #     market_trend = cryptsyMongo.getRecentMarketTrend(market_name='LTC/BTC', market_id=3)
    #     print "Market trend: {} ".format(market_trend)

if __name__ == '__main__':
    unittest.main()