from datetime import date, timedelta, datetime
import getopt
import sys
from time import sleep

import numpy
from pymongo import MongoClient

from CryptsyPy import CryptsyPy, loadCryptsyMarketData

FEE = 0.0025
BASE_STAKE = 0.001
MINIMUM_AMOUNT_TO_INVEST = 0.0005

cryptsyClient = None
mongoClient = None
mongoCryptsyDb = None
mongoMarketsCollection = None

public = ''
private = ''
userMarketIds = []
epoch = datetime.utcfromtimestamp(0)


def normalizeValues(values):
    def normalize(value, min, scalingFactor):
        return (value - min) / scalingFactor if scalingFactor != 0 else (value - min)

    minValue = min(values)
    scalingFactor = max(values) - minValue
    normalizedValues = [normalize(value, minValue, scalingFactor) for value in values]
    return normalizedValues, minValue, scalingFactor


def calculateQuantity(amountToInvest, fee, buyPrice):
    return (amountToInvest - amountToInvest * fee) / buyPrice


def getMarketTrends(filteredBtcMarkets, marketDetails):
    marketTrends = []
    marketIds = []
    for marketName in filteredBtcMarkets:
        timeStart = date.today() - timedelta(days=1)

        cryptoCurrencyDataSamples = mongoMarketsCollection.find(
            {"name": marketName, "lasttradetime": {"$gt": timeStart.strftime("%Y-%m-%d")}})

        tradeData = [(cryptoCurrencySample['lasttradetime'], cryptoCurrencySample['lasttradeprice']) for
                     cryptoCurrencySample in cryptoCurrencyDataSamples]

        uniqueTradeData = set(tradeData)

        if len(uniqueTradeData) < 200:
            continue

        times = [(datetime.strptime(tradeDataSample[0], '%Y-%m-%d %H:%M:%S') - epoch).total_seconds()
                 for
                 tradeDataSample in
                 uniqueTradeData]

        prices = [float(tradeDataSample[1]) * 100000000 for tradeDataSample in uniqueTradeData]

        normalizedTimes, minTime, timeScalingFactor = normalizeValues(times)

        normalizedPrices, minPrice, priceScalingFactor = normalizeValues(prices)

        currencyTrend = numpy.polyfit(normalizedTimes, normalizedPrices, 1)

        prices = [float(uniqueTradeDataSample[1]) for uniqueTradeDataSample in list(uniqueTradeData)]

        marketTrend = MarketTrend(marketName=marketName, marketId=marketDetails[marketName]['marketid'],
                                  m=currencyTrend[0],
                                  n=currencyTrend[1],
                                  minX=minTime,
                                  scalingFactorX=timeScalingFactor,
                                  minY=minPrice,
                                  scalingFactorY=priceScalingFactor,
                                  avg=numpy.average(prices),
                                  std=numpy.std(prices))

        marketTrends.append(marketTrend)
        marketIds.append(marketDetails[marketName]['marketid'])

    return marketTrends, marketIds


def investBTC(btcBalance, activeMarkets, marketData):
    marketNames = [market for market in marketData]

    btcMarketNames = filter(lambda x: 'BTC' in x, marketNames)

    inactiveBtcMarkets = filter(lambda x: marketData[x]['marketid'] not in activeMarkets, btcMarketNames)

    marketTrends, marketIds = getMarketTrends(inactiveBtcMarkets, marketData)

    sortedMarketTrends = filter(lambda x: x.m != 0.0 and x.avg >= 0.000001 and x.std > 4 * (x.avg * FEE),
                                sorted(marketTrends, key=lambda x: abs(0.0 - x.m)))

    bestPerformingMarkets = cryptsyClient.getBestPerformingMarketsInTheLast(3)[:4]

    worstPerformingMarkets = cryptsyClient.getWorstPerformingMarketsInTheLast(3)

    suggestedMarkets = filter(lambda x: x in marketIds, userMarketIds) + filter(lambda x: x in marketIds,
                                                                                bestPerformingMarkets)

    suggestedMarketsTrends = []

    for marketId in suggestedMarkets:
        for marketTrend in marketTrends:
            if marketTrend.marketId == marketId:
                suggestedMarketsTrends.append(marketTrend)

    otherMarketsSorted = filter(
        lambda x: x.marketId not in suggestedMarkets and x.marketId not in worstPerformingMarkets,
        sortedMarketTrends)

    marketTrendsToInvestOn = suggestedMarketsTrends + otherMarketsSorted

    for marketTrend in marketTrendsToInvestOn:

        if btcBalance < MINIMUM_AMOUNT_TO_INVEST:
            break

        if marketTrend.marketId in userMarketIds:
            desiredAmountToInvest = BASE_STAKE * 3
        elif marketTrend.marketId in bestPerformingMarkets[:2]:
            desiredAmountToInvest = BASE_STAKE * 3
        elif marketTrend.marketId in bestPerformingMarkets[2:]:
            desiredAmountToInvest = BASE_STAKE * 2

        else:
            desiredAmountToInvest = BASE_STAKE

        amountToInvest = min(desiredAmountToInvest, btcBalance)

        buyMarketTrend = getMarketTrendFor(marketTrend.marketName, marketTrend.marketId, 6)

        timeX = (datetime.now() - timedelta(hours=5) - epoch).total_seconds()
        estimatedPrice = estimateValue(timeX,
                                       buyMarketTrend.m, buyMarketTrend.n,
                                       buyMarketTrend.minX, buyMarketTrend.scalingFactorX,
                                       buyMarketTrend.minY, buyMarketTrend.scalingFactorY)

        normalizedEstimatedPrice = float(estimatedPrice) / 100000000

        buyPrice = normalizedEstimatedPrice - marketTrend.std

        quantity = calculateQuantity(amountToInvest, FEE, buyPrice)

        responseBody, apiCallSucceded = cryptsyClient.placeBuyOrder(marketTrend.marketId, quantity, buyPrice)
        if apiCallSucceded:
            btcBalance -= amountToInvest


def estimateValue(x, m, n, minX, scalingFactorX, minY, scalingFactorY):
    x_ = (float(x) - minX) / scalingFactorX
    y_ = x_ * m + n
    return y_ * scalingFactorY + minY


def getMarketTrendFor(marketName, marketId, lastXHours):
    timeStart = datetime.now() - timedelta(hours=5) - timedelta(hours=lastXHours)

    cryptoCurrencyDataSamples = mongoMarketsCollection.find(
        {"name": marketName, "lasttradetime": {"$gt": timeStart.strftime("%Y-%m-%d %H:%M:%S")}})

    tradeData = [(cryptoCurrencySample['lasttradetime'], cryptoCurrencySample['lasttradeprice']) for
                 cryptoCurrencySample in cryptoCurrencyDataSamples]
    uniqueTradeData = set(tradeData)
    times = [(datetime.strptime(tradeDataSample[0], '%Y-%m-%d %H:%M:%S') - epoch).total_seconds()
             for
             tradeDataSample in
             uniqueTradeData]
    prices = [float(tradeDataSample[1]) * 100000000 for tradeDataSample in uniqueTradeData]
    normalizedTimes, minTime, timeScalingFactor = normalizeValues(times)
    normalizedPrices, minPrice, priceScalingFactor = normalizeValues(prices)
    currencyTrend = numpy.polyfit(normalizedTimes, normalizedPrices, 1)
    prices = [float(uniqueTradeDataSample[1]) for uniqueTradeDataSample in list(uniqueTradeData)]

    marketTrend = MarketTrend(marketName=marketName,
                              marketId=marketId,
                              m=currencyTrend[0],
                              n=currencyTrend[1],
                              minX=minTime,
                              scalingFactorX=timeScalingFactor,
                              minY=minPrice,
                              scalingFactorY=priceScalingFactor,
                              avg=numpy.average(prices),
                              std=numpy.std(prices))
    return marketTrend


def initCryptsyClient():
    global cryptsyClient
    cryptsyClient = CryptsyPy(public, private)


def initMongoClient():
    global mongoClient, mongoCryptsyDb, mongoMarketsCollection
    # mongoClient = MongoClient(host="192.168.1.29")
    mongoClient = MongoClient()
    mongoCryptsyDb = mongoClient.cryptsy_database
    mongoMarketsCollection = mongoCryptsyDb.markets_collection


def splitMarkets():
    allActiveOrders = cryptsyClient.getAllActiveOrders()
    activeMarkets = []
    ordersToBeCancelled = []
    for openOrder in allActiveOrders:
        openMarketNormalized = datetime.strptime(openOrder[2], '%Y-%m-%d %H:%M:%S') + timedelta(hours=5)
        if openOrder[3] == 'Buy' and (openMarketNormalized + timedelta(hours=1)) < datetime.now():
            ordersToBeCancelled.append(openOrder[1])
        elif openOrder[3] == 'Sell' and (openMarketNormalized + timedelta(hours=1)) < datetime.now():
            ordersToBeCancelled.append(openOrder[1])
            activeMarkets.append(openOrder[0])
        else:
            activeMarkets.append(openOrder[0])
    return activeMarkets, ordersToBeCancelled


def placeSellOrder(marketName, marketId, quantity):
    marketTrend = getMarketTrendFor(marketName, marketId, 6)
    timeX = (datetime.now() - timedelta(hours=5) - epoch).total_seconds()
    estimatedPrice = estimateValue(timeX,
                                   marketTrend.m, marketTrend.n,
                                   marketTrend.minX, marketTrend.scalingFactorX,
                                   marketTrend.minY, marketTrend.scalingFactorY)
    normalizedEstimatedPrice = float(estimatedPrice) / 100000000
    sellPrice = normalizedEstimatedPrice + marketTrend.std

    if quantity * sellPrice >= 0.00000010:
        cryptsyClient.placeSellOrder(marketTrend.marketId, quantity, sellPrice)
    else:
        print "Order is less than 0.00000010: {}".format(quantity * sellPrice)


def main(argv):
    print "Started."

    getEnv(argv)

    initCryptsyClient()

    initMongoClient()

    activeMarkets, ordersToBeCancelled = splitMarkets()

    for orderToBeCancelled in ordersToBeCancelled:
        cryptsyClient.cancelOrder(orderToBeCancelled)

    # Wait for cancellations to take place
    sleep(5)

    balanceList = filter(lambda x: x[0] != 'Points', cryptsyClient.getInfo())
    print "Current Balance:"
    for balance in balanceList:
        print "{}, {}".format(balance[0], balance[1])

    marketData = loadCryptsyMarketData()

    btcBalance = 0.0
    for balance in balanceList:
        if balance[0] == 'BTC':
            btcBalance = balance[1]
        else:
            marketName = "{}/BTC".format(balance[0])
            marketId = marketData[marketName]['marketid']
            placeSellOrder(marketName, marketId, balance[1])

    if btcBalance >= MINIMUM_AMOUNT_TO_INVEST:
        investBTC(btcBalance, activeMarkets, marketData)

    print "Complete"


class MarketTrend:
    def __init__(self, marketName, marketId, m, n, minX, scalingFactorX, minY, scalingFactorY, avg, std):
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


def getEnv(argv):
    global public
    global private
    global userMarketIds
    try:
        opts, args = getopt.getopt(argv, "h", ["help", "public=", "private=", "marketIds="])
    except getopt.GetoptError:
        sys.exit(2)
    for opt, arg in opts:
        if opt in ("-h", "--help"):
            sys.exit()
        elif opt == "--public":
            public = arg
        elif opt == "--private":
            private = arg
        elif opt == "--marketIds":
            userMarketIds = arg.split(",")


if __name__ == "__main__":
    main(sys.argv[1:])