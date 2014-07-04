from datetime import date, timedelta, datetime
import time
import getopt
import sys

import numpy
from pymongo import MongoClient

from CryptsyPy import CryptsyPy, loadCryptsyMarketData


AMOUNT_TO_INVEST = 0.001

cryptsyClient = None
mongoClient = None
mongoCryptsyDb = None
mongoMarketsCollection = None

public = ''
private = ''
epoch = datetime.utcfromtimestamp(0)


def getNormalizedTimesAndPrices(tradeData):
    def normalize(value, min, scalingFactor):
        return (value - min) / scalingFactor if scalingFactor != 0 else (value - min)

    def normalizeValues(values):
        minValue = min(values)
        scalingFactor = max(values) - minValue
        normalizedValues = [normalize(value, minValue, scalingFactor) for value in values]
        return normalizedValues

    lastTradeTimes = [(datetime.strptime(tradeDataSample[0], '%Y-%m-%d %H:%M:%S') - epoch).total_seconds()
                      for
                      tradeDataSample in
                      tradeData]

    lastTradePrices = [float(tradeDataSample[1]) * 100000000 for tradeDataSample in tradeData]

    return normalizeValues(lastTradePrices), normalizeValues(lastTradeTimes)


def calculateQuantity(amountToInvest, fee, buyPrice):
    return (amountToInvest - amountToInvest * fee) / buyPrice


def investBTC(btcBalance, bestPerformingMarkets, openBuyMarkets, cryptsyMarketData):
    marketDetails = cryptsyMarketData['return']['markets']
    marketNames = [market for market in marketDetails]
    timeStart = date.today() - timedelta(days=1)
    btcMarketNames = filter(lambda x: 'BTC' in x, marketNames)
    marketTrends = []

    filteredBtcMarkets = filter(lambda x: marketDetails[x]['marketid'] not in openBuyMarkets, btcMarketNames)

    for marketName in filteredBtcMarkets:

        cryptoCurrencyDataSamples = mongoMarketsCollection.find(
            {"name": marketName, "lasttradetime": {"$gt": timeStart.strftime("%Y-%m-%d")}})

        tradeData = [(cryptoCurrencySample['lasttradetime'], cryptoCurrencySample['lasttradeprice']) for
                     cryptoCurrencySample in cryptoCurrencyDataSamples]

        uniqueTradeData = set(tradeData)

        if len(uniqueTradeData) < 200:
            continue

        normalizedLastTradePrices, normalizedLastTradeTimes = getNormalizedTimesAndPrices(set(uniqueTradeData))

        currencyTrend = numpy.polyfit(normalizedLastTradeTimes, normalizedLastTradePrices, 1)

        prices = [float(uniqueTradeDataSample[1]) for uniqueTradeDataSample in list(uniqueTradeData)]

        marketTrend = MarketTrend(marketName=marketName, marketId=marketDetails[marketName]['marketid'],
                                  m=currencyTrend[0],
                                  avg=numpy.average(prices),
                                  std=numpy.std(prices))

        marketTrends.append(marketTrend)

    sortedMarketTrends = filter(lambda x: x.m != 0.0 and x.avg >= 0.000001 and x.std > 4 * 0.0025 * x.avg,
                                sorted(marketTrends, key=lambda x: abs(0.0 - x.m)))

    firstTenSorted = filter(lambda x: x.marketId in bestPerformingMarkets, sortedMarketTrends[:25])

    otherMarketsSorted = filter(lambda x: x.marketId not in bestPerformingMarkets, sortedMarketTrends)

    orderedMarketsToInvestOn = firstTenSorted + otherMarketsSorted

    for marketTrend in orderedMarketsToInvestOn:

        if btcBalance < AMOUNT_TO_INVEST:
            break

        ## Market.buy has to be calculate a bit more smartly with the trending function.
        quantity = calculateQuantity(AMOUNT_TO_INVEST, 0.0025, marketTrend.buy)

        responseBody, apiCallSucceded = cryptsyClient.placeBuyOrder(marketTrend.marketId, quantity, marketTrend.buy)
        if apiCallSucceded:
            btcBalance -= AMOUNT_TO_INVEST


def main(argv):
    print "Started."

    getEnv(argv)

    global cryptsyClient
    cryptsyClient = CryptsyPy(public, private)

    global mongoClient, mongoCryptsyDb, mongoMarketsCollection
    mongoClient = MongoClient(host="192.168.1.29")
    mongoCryptsyDb = mongoClient.cryptsy_database
    mongoMarketsCollection = mongoCryptsyDb.markets_collection

    bestPerformingMarkets = cryptsyClient.getBestPerformingMarketsInTheLast(1, 1)

    openBuyMarketsDetails = cryptsyClient.getAllActiveOrders()
    openBuyMarkets = []
    for openBuyMarketsDetail in openBuyMarketsDetails:
        openMarketNormalized = datetime.strptime(openBuyMarketsDetail[2], '%Y-%m-%d %H:%M:%S') + timedelta(hours=4)
        if openBuyMarketsDetail[3] == 'Buy' and (openMarketNormalized + timedelta(hours=1)) < datetime.now():
            postData = "method={}&orderid={}&nonce={}".format("cancelorder", openBuyMarketsDetail[1], int(time.time()))
            cryptsyClient.makeAPIcall(postData)
        elif openBuyMarketsDetail[3] == 'Sell' and (openMarketNormalized + timedelta(hours=3)) < datetime.now():
            postData = "method={}&orderid={}&nonce={}".format("cancelorder", openBuyMarketsDetail[1], int(time.time()))
            cryptsyClient.makeAPIcall(postData)
            openBuyMarkets.append(openBuyMarketsDetail[0])
        else:
            openBuyMarkets.append(openBuyMarketsDetail[0])

    balanceList = cryptsyClient.getInfo()

    print "Current Balance:"
    for balance in balanceList:
        print "{}, {}".format(balance[0], balance[1])

    cryptsyMarketData = loadCryptsyMarketData()

    investBTCFlag = False

    filteredBalanceList = filter(lambda x: x[0] != 'Points', balanceList)

    btcBalance = 0.0
    for balance in filteredBalanceList:

        if balance[0] == 'BTC':
            btcBalance = balance[1]
            investBTCFlag = True
        else:

            marketName = "{}/BTC".format(balance[0])

            timeStart = date.today() - timedelta(days=1)

            cryptoCurrencyDataSamples = mongoMarketsCollection.find(
                {"name": marketName, "lasttradetime": {"$gt": timeStart.strftime("%Y-%m-%d")}})

            prices = [float(cryptoCurrencyDataSample['lasttradeprice']) for cryptoCurrencyDataSample in
                      cryptoCurrencyDataSamples]

            # Is the price at which I expect to make some profit
            ## Market.buy has to be calculate a bit more smartly with the trending function.
            sell = numpy.average(prices) + numpy.std(prices)

            marketId = cryptsyMarketData['return']['markets'][marketName]['marketid']
            quantity = balance[1]
            cryptsyClient.placeSellOrder(marketId, quantity, sell)

    if investBTCFlag:
        if btcBalance >= AMOUNT_TO_INVEST:
            investBTC(btcBalance, bestPerformingMarkets, openBuyMarkets, cryptsyMarketData)

    print "Complete"


class MarketTrend:
    def __init__(self, marketName, marketId, m, avg, std):
        self.marketName = marketName
        self.marketId = marketId
        self.m = m
        self.avg = avg
        self.std = std
        self.buy = avg - std
        self.sell = avg + std

    def __str__(self):
        return "marketName: {}, id: {}, m: {}, avg: {}, std: {}, buy: {}, sell: {}".format(
            self.marketName,
            self.marketId,
            self.m,
            self.avg,
            self.std,
            self.buy,
            self.sell
        )


def getEnv(argv):
    global public
    global private
    try:
        opts, args = getopt.getopt(argv, "h", ["help", "public=", "private="])
    except getopt.GetoptError:
        sys.exit(2)
    for opt, arg in opts:
        if opt in ("-h", "--help"):
            sys.exit()
        elif opt == "--public":
            public = arg
        elif opt == "--private":
            private = arg


if __name__ == "__main__":
    main(sys.argv[1:])