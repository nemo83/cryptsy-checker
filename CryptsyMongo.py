from datetime import timedelta, datetime
import numpy

from pymongo import MongoClient

epoch = datetime.utcfromtimestamp(0)


class CryptsyMongo:
    def __init__(self, host='127.0.0.1', timezone_delta=timedelta(hours=5)):
        self.host = host
        self.timezone_delta = timezone_delta
        self.mongo_client = MongoClient(host=host)
        self.mongo_cryptsy_db = self.mongo_client.cryptsy_database
        self.markets_collection = self.mongo_cryptsy_db.markets_collection
        self.market_trend_collection = self.mongo_cryptsy_db.market_trend_collection

    def truncate_market_trend_collection(self):
        self.market_trend_collection.remove()

    def getRecentMarketTrend(self, market_name, market_id, timedelta=timedelta(hours=1), force_update=False):
        time_start = datetime.now() - timedelta

        market_trends = self.market_trend_collection.find({"marketName": market_name}).sort('time', -1).limit(1)

        if not force_update and market_trends.count() > 0 and time_start < datetime.strptime(market_trends[0]['time'],
                                                                                             "%Y-%m-%d %H:%M:%S"):
            market_trend = MarketTrend(marketName=market_trends[0]['marketName'],
                                       marketId=int(market_trends[0]['marketId']),
                                       m=float(market_trends[0]['m']),
                                       n=float(market_trends[0]['n']),
                                       minX=float(market_trends[0]['minX']),
                                       scalingFactorX=float(market_trends[0]['scalingFactorX']),
                                       minY=float(market_trends[0]['minY']),
                                       scalingFactorY=float(market_trends[0]['scalingFactorY']),
                                       avg=float(market_trends[0]['avg']),
                                       std=float(market_trends[0]['std']))
        else:
            market_trend = self.calculateMarketTrend(market_name, market_id)
            market_trend_dict = market_trend.__dict__
            market_trend_dict['time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.market_trend_collection.insert(market_trend_dict)

        return market_trend


    def calculateMarketTrend(self, market_name, market_id, interval=timedelta(days=1, hours=5),
                             check_num_samples=True):

        timeStart = datetime.now() - interval

        numTrades = self.markets_collection.find(
            {"name": market_name, "lasttradetime": {"$gt": timeStart.strftime("%Y-%m-%d %H:%M:%S")}}).count()

        if numTrades < 100:
            print "Low num samples for {} on mongo ({})".format(market_name, numTrades)
            if numTrades == 0 or check_num_samples:
                return MarketTrend(marketName=market_name, marketId=market_id)

        cryptoCurrencyDataSamples = self.markets_collection.find(
            {"name": market_name, "lasttradetime": {"$gt": timeStart.strftime("%Y-%m-%d %H:%M:%S")}})

        tradeData = [(cryptoCurrencySample['lasttradetime'], cryptoCurrencySample['lasttradeprice']) for
                     cryptoCurrencySample in cryptoCurrencyDataSamples]

        uniqueTradeData = set(tradeData)

        if len(uniqueTradeData) < 80:
            print "Low num samples for {} ({})".format(market_name, len(uniqueTradeData))
            if numTrades == 0 or check_num_samples:
                return MarketTrend(marketName=market_name, marketId=market_id)

        times = [(datetime.strptime(tradeDataSample[0], '%Y-%m-%d %H:%M:%S') - epoch).total_seconds()
                 for
                 tradeDataSample in
                 uniqueTradeData]

        prices = [float(tradeDataSample[1]) * 100000000 for tradeDataSample in uniqueTradeData]

        normalizedTimes, minTime, timeScalingFactor = normalizeValues(times)

        normalizedPrices, minPrice, priceScalingFactor = normalizeValues(prices)

        currencyTrend = numpy.polyfit(normalizedTimes, normalizedPrices, 1)

        prices = [float(uniqueTradeDataSample[1]) for uniqueTradeDataSample in list(uniqueTradeData)]

        marketTrend = MarketTrend(marketName=market_name, marketId=market_id,
                                  m=currencyTrend[0],
                                  n=currencyTrend[1],
                                  minX=minTime,
                                  scalingFactorX=timeScalingFactor,
                                  minY=minPrice,
                                  scalingFactorY=priceScalingFactor,
                                  avg=numpy.average(prices),
                                  std=numpy.std(prices))

        return marketTrend


class MarketTrend:
    def __init__(self, marketName, marketId, m=0.0, n=0.0, minX=0.0, scalingFactorX=0.0, minY=0.0, scalingFactorY=0.0,
                 avg=0.0, std=0.0):
        self.marketName = marketName
        self.marketId = marketId
        self.m = m
        self.n = n
        self.minX = minX
        self.scalingFactorX = scalingFactorX
        self.minY = minY
        self.scalingFactorY = scalingFactorY
        self.avg = avg
        self.std = std
        self.buy = avg - std
        self.sell = avg + std

    def __str__(self):
        return "marketName: {}, id: {}, m: {}, n: {}, minX: {}, scalingFactorX: {}, minY: {}, scalingFactorY: {}, avg: {}, std: {}, buy: {}, sell: {}".format(
            self.marketName,
            self.marketId,
            self.m,
            self.n,
            self.minX,
            self.scalingFactorX,
            self.minY,
            self.scalingFactorY,
            self.std,
            self.buy,
            self.sell
        )


def normalizeValues(values):
    def normalize(value, min, scalingFactor):
        return (value - min) / scalingFactor if scalingFactor != 0 else (value - min)

    minValue = min(values)
    scalingFactor = max(values) - minValue
    normalizedValues = [normalize(value, minValue, scalingFactor) for value in values]
    return normalizedValues, minValue, scalingFactor