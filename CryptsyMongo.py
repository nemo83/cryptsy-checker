from datetime import timedelta, datetime
import logging

import numpy
from pymongo import MongoClient

logger = logging.getLogger("bot_logger")

epoch = datetime.utcfromtimestamp(0)


def toTenDigit(value):
    return "%.10f" % round(value, 10)


class CryptsyMongo:
    def __init__(self, host='127.0.0.1', timezone_delta=timedelta(hours=4)):
        self.host = host
        self.timezone_delta = timezone_delta
        self.mongo_client = MongoClient(host=host)
        self.mongo_cryptsy_db = self.mongo_client.cryptsy_database
        self.markets_collection = self.mongo_cryptsy_db.markets_collection
        self.market_trend_collection = self.mongo_cryptsy_db.market_trend_collection
        self.trades_collection = self.mongo_cryptsy_db.trades_collection

    def truncate_market_trend_collection(self):
        self.market_trend_collection.remove()

    def getRecentMarketTrends(self, timedelta=timedelta(minutes=15)):
        time_start = datetime.utcnow() - timedelta

        mongo_market_trends = self.market_trend_collection.find(
            {"time": {"$gt": time_start.strftime("%Y-%m-%d %H:%M:%S")}})

        market_trends = []

        for mongo_market_trend in mongo_market_trends:
            market_trends.append(MarketTrend(marketName=mongo_market_trend['marketName'],
                                             marketId=int(mongo_market_trend['marketId']),
                                             m=float(mongo_market_trend['m']),
                                             n=float(mongo_market_trend['n']),
                                             minX=float(mongo_market_trend['minX']),
                                             scalingFactorX=float(mongo_market_trend['scalingFactorX']),
                                             minY=float(mongo_market_trend['minY']),
                                             scalingFactorY=float(mongo_market_trend['scalingFactorY']),
                                             avg=float(mongo_market_trend['avg']),
                                             std=float(mongo_market_trend['std']),
                                             num_samples=mongo_market_trend['num_samples'],
                                             sample_time=mongo_market_trend['sample_time']))

        filtered_market_trends = filter(lambda x: datetime.strptime(x.sample_time, "%Y-%m-%d %H:%M:%S") == max(
            [datetime.strptime(z.sample_time, "%Y-%m-%d %H:%M:%S") for z in
             filter(lambda y: y.marketName == x.marketName, market_trends)]), market_trends)

        return filtered_market_trends

    def persistMarketTrend(self, market_trend):
        market_trend_dict = market_trend.__dict__
        market_trend_dict['time'] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        self.market_trend_collection.insert(market_trend_dict)

    def calculateMarketTrend(self, market_name, market_id, interval=timedelta(days=1, hours=4)):

        start_time = datetime.utcnow() - interval

        cryptoCurrencyDataSamples = self.markets_collection.find(
            {"name": market_name, "lasttradetime": {"$gt": start_time.strftime("%Y-%m-%d %H:%M:%S")}})

        tradeData = [(cryptoCurrencySample['lasttradetime'], cryptoCurrencySample['lasttradeprice']) for
                     cryptoCurrencySample in cryptoCurrencyDataSamples]

        uniqueTradeData = set(tradeData)

        num_samples = len(uniqueTradeData)

        if num_samples == 0:
            return MarketTrend(market_name, market_id)

        times = [(datetime.strptime(tradeDataSample[0], '%Y-%m-%d %H:%M:%S') - epoch).total_seconds()
                 for
                 tradeDataSample in
                 uniqueTradeData]

        prices = [float(tradeDataSample[1]) * 100000000 for tradeDataSample in uniqueTradeData]

        normalizedTimes, minTime, timeScalingFactor = normalizeValues(times)

        normalizedPrices, minPrice, priceScalingFactor = normalizeValues(prices)

        if priceScalingFactor == 0.0 or timeScalingFactor == 0.0:
            logger.info("priceScalingFactor: {}, timeScalingFactor: {}".format(priceScalingFactor, timeScalingFactor))
            return MarketTrend(market_name, market_id)

        trend = numpy.polyfit(normalizedTimes, normalizedPrices, 1)

        unique_prices = [float(uniqueTradeDataSample[1]) for uniqueTradeDataSample in list(uniqueTradeData)]

        trend_normalized_prices = [price - (
            self.estimateValue(times[index], trend[0], trend[1], minTime, timeScalingFactor, minPrice,
                               priceScalingFactor)) for index, price in enumerate(prices)]

        trend_normalized_prices = [float(translated_price) / 100000000 for translated_price in trend_normalized_prices]

        marketTrend = MarketTrend(marketName=market_name, marketId=market_id,
                                  m=trend[0],
                                  n=trend[1],
                                  minX=minTime,
                                  scalingFactorX=timeScalingFactor,
                                  minY=minPrice,
                                  scalingFactorY=priceScalingFactor,
                                  avg=numpy.average(unique_prices),
                                  std=numpy.std(trend_normalized_prices),
                                  num_samples=num_samples)

        return marketTrend

    def estimateValue(self, x, m, n, minX, scalingFactorX, minY, scalingFactorY):
        x_ = (float(x) - minX) / scalingFactorX
        y_ = x_ * m + n
        return y_ * scalingFactorY + minY

    def getNormalizedEstimatedPrice(self, market_trend, price_time=datetime.utcnow()):
        timeX = (price_time - self.timezone_delta - epoch).total_seconds()
        estimatedPrice = self.estimateValue(timeX,
                                            market_trend.m, market_trend.n,
                                            market_trend.minX, market_trend.scalingFactorX,
                                            market_trend.minY, market_trend.scalingFactorY)
        normalizedEstimatedPrice = float(estimatedPrice) / 100000000
        return normalizedEstimatedPrice

    def persistTrades(self, trades):
        latest_trade = next(self.trades_collection.find().sort('tradeid', -1).limit(1), None)
        last_trade_id = 0 if latest_trade is None else latest_trade['tradeid']
        for trade in trades:
            if trade['tradeid'] > last_trade_id:
                self.trades_collection.insert(trade)

    def getLastTrades(self, time_start=(datetime.utcnow() - timedelta(hours=24))):
        return self.trades_collection.find({"datetime": {"$gt": time_start.strftime("%Y-%m-%d %H:%M:%S")}}).sort(
            'tradeid', 1)


    def getAllTradesFrom(self, time_start):

        mongo_trade_stats = self.getLastTrades(time_start)

        trade_stats = {}
        for trade_stat in mongo_trade_stats:
            market_id = trade_stat['marketid']
            trade_type = trade_stat['tradetype']

            if trade_type == 'Sell' and market_id not in trade_stats:
                continue
            elif market_id not in trade_stats:
                trade_stats[market_id] = []

            trade_stats[market_id].append(trade_stat)

        for trade_stat in trade_stats:
            while len(trade_stats[trade_stat]) > 0 and trade_stats[trade_stat][-1]['tradetype'] == 'Buy':
                trade_stats[trade_stat].pop()

        indexes_to_be_removed = [trade_stat for trade_stat in trade_stats if len(trade_stats[trade_stat]) == 0]

        for index in indexes_to_be_removed:
            trade_stats.pop(index, None)

        trade_results = {}
        for market_id in trade_stats:
            activities = map(
                lambda trade_stat: (float(trade_stat['total']) if trade_stat['tradetype'] == 'Buy' else 0.0,
                                    float(trade_stat['total']) if trade_stat['tradetype'] == 'Sell' else 0.0,
                                    float(trade_stat['fee']), 1),
                trade_stats[market_id])

            reduction = reduce(lambda x, y: (x[0] + y[0], x[1] + y[1], x[2] + y[2], x[3] + y[3]), activities,
                               (0.0, 0.0, 0.0, 0))

            trade_results[market_id] = {}
            trade_results[market_id]['NumTrades'] = reduction[3]
            trade_results[market_id]['Buy'] = reduction[0]
            trade_results[market_id]['Sell'] = reduction[1]
            trade_results[market_id]['Fee'] = reduction[2]

        return trade_results

    def getMarketsMultipliers(self, time_start=(datetime.utcnow() - timedelta(hours=6))):

        mongo_trade_stats = self.getLastTrades(time_start)

        trade_stats = {}
        for trade_stat in mongo_trade_stats:
            market_id = trade_stat['marketid']
            if market_id not in trade_stats:
                trade_stats[market_id] = []
            trade_stats[market_id].append(trade_stat)

        for trade_stat in trade_stats:
            while len(trade_stats[trade_stat]) > 0 and trade_stats[trade_stat][0]['tradetype'] == 'Sell':
                trade_stats[trade_stat].pop(0)

        for trade_stat in trade_stats:
            while len(trade_stats[trade_stat]) > 0 and trade_stats[trade_stat][-1]['tradetype'] == 'Buy':
                trade_stats[trade_stat].pop()

        indexes_to_be_removed = [trade_stat for trade_stat in trade_stats if len(trade_stats[trade_stat]) == 0]

        for index in indexes_to_be_removed:
            trade_stats.pop(index, None)

        multipliers = {}
        for market_id in trade_stats:
            activities = map(
                lambda trade_stat: (trade_stat['tradetype'], float(trade_stat['total']), float(trade_stat['fee']), 0),
                trade_stats[market_id])

            multiplier_counter = 0
            income = 0.0
            sales_in_transaction_detected = False

            for activity in activities:
                if activity[0] == "Buy" and not sales_in_transaction_detected:
                    income -= activity[1] + activity[2]
                elif activity[0] == "Buy" and sales_in_transaction_detected:
                    if income > 0:
                        multiplier_counter += 1
                    else:
                        multiplier_counter = -1
                    income = 0
                    sales_in_transaction_detected = False
                else:
                    income += activity[1] - activity[2]
                    sales_in_transaction_detected = True

            if sales_in_transaction_detected:
                if income > 0:
                    multiplier_counter += 1
                else:
                    multiplier_counter = -1

            multipliers[int(market_id)] = {}
            # multipliers[int(market_id)] = multiplier_counter if not last_transaction_negative else 0
            multipliers[int(market_id)] = multiplier_counter

        return multipliers

    def getBestPerformingMarketsFrom(self, start_time):
        tradeStats = self.getAllTradesFrom(start_time)
        filteredTradeStats = filter(lambda x: tradeStats[x]['Sell'] >= tradeStats[x]['Fee'] + tradeStats[x]['Buy'],
                                    tradeStats)
        sortedTradeStats = sorted(filteredTradeStats, key=lambda x: tradeStats[x]['Sell'] - tradeStats[x]['Buy'],
                                  reverse=True)
        return sortedTradeStats

    def getWorstPerformingMarketsFrom(self, start_time):
        tradeStats = self.getAllTradesFrom(start_time)
        filteredTradeStats = filter(lambda x: 0 < tradeStats[x]['Sell'] < tradeStats[x]['Fee'] + tradeStats[x]['Buy'],
                                    tradeStats)
        sortedTradeStats = sorted(filteredTradeStats, key=lambda x: tradeStats[x]['Sell'] - tradeStats[x]['Buy'])

        return sortedTradeStats


class MarketTrend:
    def __init__(self, marketName, marketId, m=0.0, n=0.0, minX=0.0, scalingFactorX=0.0, minY=0.0, scalingFactorY=0.0,
                 avg=0.0, std=0.0, num_samples=0, sample_time=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")):
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
        self.num_samples = num_samples
        self.sample_time = sample_time

    def __str__(self):
        return "marketName: {}, id: {}, m: {}, n: {}, minX: {}, scalingFactorX: {}, minY: {}, scalingFactorY: {}, avg: {}, std: {}, num samples: {}, sample_time: {}".format(
            self.marketName,
            self.marketId,
            self.m,
            self.n,
            self.minX,
            self.scalingFactorX,
            self.minY,
            self.scalingFactorY,
            self.avg,
            self.std,
            self.num_samples,
            self.sample_time
        )

    def __eq__(self, other):
        return (isinstance(other, self.__class__)
                and self.marketName == other.marketName
                and self.marketId == other.marketId
                and self.m == other.m
                and self.n == other.n
                and self.minX == other.minX
                and self.scalingFactorX == other.scalingFactorX
                and self.minY == other.minY
                and self.scalingFactorY == other.scalingFactorY
                and self.std == other.std
                and self.num_samples == other.num_samples)

    def __ne__(self, other):
        return not self.__eq__(other)


def normalizeValues(values):
    def normalize(value, min, scalingFactor):
        return (value - min) / scalingFactor if scalingFactor != 0 else (value - min)

    minValue = min(values)
    scalingFactor = max(values) - minValue
    normalizedValues = [normalize(value, minValue, scalingFactor) for value in values]
    return normalizedValues, minValue, scalingFactor