from datetime import timedelta, datetime
import getopt
import sys
import os
from time import sleep

from pymongo import MongoClient

from CryptsyPy import CryptsyPy, toEightDigit
from CryptsyMongo import CryptsyMongo

FEE = 0.0025
BASE_STAKE = 0.00025
MINIMUM_AMOUNT_TO_INVEST = 0.00025

sell_only = False

cryptsyClient = None
mongoClient = None
mongoCryptsyDb = None
mongoMarketsCollection = None

cryptsy_mongo = None

public = ''
private = ''
userMarketIds = []
epoch = datetime.utcfromtimestamp(0)

CRYPTSY_HOURS_DIFFERENCE = 4


def toCryptsyServerTime(time):
    return time + timedelta(hours=CRYPTSY_HOURS_DIFFERENCE)


def fromCryptsyServerTime(time):
    return time - timedelta(hours=CRYPTSY_HOURS_DIFFERENCE)


def normalizeValues(values):
    def normalize(value, min, scalingFactor):
        return (value - min) / scalingFactor if scalingFactor != 0 else (value - min)

    minValue = min(values)
    scalingFactor = max(values) - minValue
    normalizedValues = [normalize(value, minValue, scalingFactor) for value in values]
    return normalizedValues, minValue, scalingFactor


def calculateQuantity(amountToInvest, fee, buyPrice):
    return (amountToInvest - amountToInvest * fee) / buyPrice


def getMarketTrends(filteredBtcMarkets, markets):
    marketTrends = []
    marketIds = []
    for marketName in filteredBtcMarkets:
        marketTrend = cryptsy_mongo.getRecentMarketTrend(market_name=marketName,
                                                         market_id=markets[marketName])
        if marketTrend.m != 0.0:
            marketTrends.append(marketTrend)
            marketIds.append(markets[marketName])

    return marketTrends, marketIds


def investBTC(btcBalance, activeMarkets, markets):
    marketNames = [market for market in markets]

    btcMarketNames = filter(lambda x: 'BTC' in x and 'Points' not in x, marketNames)

    inactiveBtcMarkets = filter(lambda x: markets[x] not in activeMarkets, btcMarketNames)

    marketTrends, marketIds = getMarketTrends(inactiveBtcMarkets, markets)

    sortedMarketTrends = filter(lambda x: x.m != 0.0 and x.avg >= 0.0000001 and x.std > 4 * (x.avg * FEE),
                                sorted(marketTrends, key=lambda x: abs(0.0 - x.m)))

    bestPerformingMarkets = cryptsyClient.getBestPerformingMarketsInTheLastFeeIncluded(3)[:6]

    worstPerformingMarkets = cryptsyClient.getWorstPerformingMarketsInTheLastFeeIncluded(3)

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
            desiredAmountToInvest = BASE_STAKE
        elif marketTrend.marketId in bestPerformingMarkets[:1]:
            desiredAmountToInvest = BASE_STAKE * 12
        elif marketTrend.marketId in bestPerformingMarkets[1:2]:
            desiredAmountToInvest = BASE_STAKE * 6
        elif marketTrend.marketId in bestPerformingMarkets[2:3]:
            desiredAmountToInvest = BASE_STAKE * 4
        elif marketTrend.marketId in bestPerformingMarkets[3:]:
            desiredAmountToInvest = BASE_STAKE * 2

        else:
            desiredAmountToInvest = BASE_STAKE

        amountToInvest = min(desiredAmountToInvest, btcBalance)

        buyMarketTrend = getMarketTrendFor(marketTrend.marketName, marketTrend.marketId, 6)

        if buyMarketTrend.m == 0.0:
            print "Market {} has default 0 m, no order will be open".format(marketTrend.marketName)
            continue

        timeX = (toCryptsyServerTime(datetime.now()) - epoch).total_seconds()

        estimatedPrice = estimateValue(timeX,
                                       buyMarketTrend.m, buyMarketTrend.n,
                                       buyMarketTrend.minX, buyMarketTrend.scalingFactorX,
                                       buyMarketTrend.minY, buyMarketTrend.scalingFactorY)

        normalizedEstimatedPrice = float(estimatedPrice) / 100000000

        buyPrice = normalizedEstimatedPrice - marketTrend.std

        quantity = calculateQuantity(amountToInvest, FEE, buyPrice)

        if buyPrice <= 0.0 or quantity <= 0.0:
            print "Attempting to buy: {} {}, at price: {} - Order will not be placed.".format(quantity,
                                                                                              marketTrend.marketName,
                                                                                              buyPrice)
            continue

        responseBody, apiCallSucceded = cryptsyClient.placeBuyOrder(marketTrend.marketId, quantity, buyPrice)
        if apiCallSucceded:
            btcBalance -= amountToInvest


def estimateValue(x, m, n, minX, scalingFactorX, minY, scalingFactorY):
    x_ = (float(x) - minX) / scalingFactorX
    y_ = x_ * m + n
    return y_ * scalingFactorY + minY


def getMarketTrendFor(marketName, marketId, lastXHours, reliable=True):
    return cryptsy_mongo.calculateMarketTrend(market_name=marketName,
                                              market_id=marketId,
                                              interval=timedelta(hours=CRYPTSY_HOURS_DIFFERENCE + lastXHours),
                                              check_num_samples=reliable)


def initCryptsyClient():
    global cryptsyClient
    cryptsyClient = CryptsyPy(public, private)


def initMongoClient():
    global mongoClient, mongoCryptsyDb, mongoMarketsCollection, cryptsy_mongo
    # mongoClient = MongoClient(host="192.168.1.29")
    mongoClient = MongoClient()
    mongoCryptsyDb = mongoClient.cryptsy_database
    mongoMarketsCollection = mongoCryptsyDb.markets_collection

    # cryptsy_mongo = CryptsyMongo(host="192.168.1.29")
    cryptsy_mongo = CryptsyMongo()


def splitMarkets(markets):
    allActiveOrders = cryptsyClient.getAllActiveOrders()
    activeMarkets = []
    ordersToBeCancelled = []
    for openOrder in allActiveOrders:
        openMarketNormalized = fromCryptsyServerTime(datetime.strptime(openOrder[2], '%Y-%m-%d %H:%M:%S'))
        if openOrder[3] == 'Buy' and (openMarketNormalized + timedelta(hours=1)) < datetime.now():
            ordersToBeCancelled.append(openOrder[1])
        elif openOrder[3] == 'Sell' and (openMarketNormalized + timedelta(minutes=30)) < datetime.now():

            market_name = next((market_name for market_name in markets if (markets[market_name] == openOrder[0])), None)

            market_trend = getMarketTrendFor(market_name, openOrder[0], 6, False)

            timeX = (toCryptsyServerTime(datetime.now()) - epoch).total_seconds()
            estimatedPrice = estimateValue(timeX,
                                           market_trend.m, market_trend.n,
                                           market_trend.minX, market_trend.scalingFactorX,
                                           market_trend.minY, market_trend.scalingFactorY)
            normalizedEstimatedPrice = float(estimatedPrice) / 100000000
            sellPrice = normalizedEstimatedPrice + market_trend.std

            if float(toEightDigit(sellPrice)) != float(openOrder[4]):
                print "Cancelling order for {} market. Old Price: {}, New Price: {}".format(market_name, openOrder[4],
                                                                                            sellPrice)
                ordersToBeCancelled.append(openOrder[1])
                activeMarkets.append(openOrder[0])
            else:
                print "Sell order expired but not deleted for {} market. Old Price: {}, New Price: {}".format(
                    market_name, openOrder[4], sellPrice)
        else:
            activeMarkets.append(openOrder[0])
    return activeMarkets, ordersToBeCancelled


def placeSellOrder(marketName, marketId, quantity):
    marketTrend = getMarketTrendFor(marketName, marketId, 6, reliable=False)
    if marketTrend.m == 0.0:
        print "No sell order for market {} will be placed. Not enough sale info.".format(marketName)
        return
    timeX = (toCryptsyServerTime(datetime.now()) - epoch).total_seconds()
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
    getEnv(argv)

    initCryptsyClient()

    initMongoClient()

    markets = cryptsyClient.getMarkets()

    activeMarkets, ordersToBeCancelled = splitMarkets(markets)

    for orderToBeCancelled in ordersToBeCancelled:
        cryptsyClient.cancelOrder(orderToBeCancelled)

        # Wait for cancellations to take place
    sleep(5)

    balanceList = filter(lambda x: x[0] != 'Points', cryptsyClient.getInfo())
    print "Current Balance:"
    for balance in balanceList:
        print "{}, {}".format(balance[0], balance[1])

    btcBalance = 0.0
    for balance in balanceList:
        if balance[0] == 'BTC':
            btcBalance = balance[1]
        else:
            marketName = "{}/BTC".format(balance[0])
            marketId = markets[marketName]
            placeSellOrder(marketName, marketId, balance[1])

    if sell_only:
        print "Sell only flag active. No buy trade will be open. Returning..."
    elif btcBalance >= MINIMUM_AMOUNT_TO_INVEST:
        investBTC(btcBalance, activeMarkets, markets)
    else:
        print "Not enough funds. Exiting"

    print "Complete"


def getEnv(argv):
    global public
    global private
    global userMarketIds
    global sell_only
    try:
        opts, args = getopt.getopt(argv, "h", ["help", "public=", "private=", "marketIds=", "sellOnly"])
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
        elif opt == "--sellOnly":
            sell_only = True


if __name__ == "__main__":
    starttime = datetime.now()
    print "Started at {}".format(starttime)
    lock_filename = "bot.lock"
    if os.path.isfile(lock_filename):
        print "Bot already running. Exiting..."
        sys.exit(0)

    lock_file = open(lock_filename, "w+")
    lock_file.close()

    try:
        main(sys.argv[1:])
    except:
        print "Unexpected error: {}".format(sys.exc_info()[0])

    elapsed = datetime.now() - starttime

    print "Finished at {}".format(datetime.now())
    print "Execution took: {}".format(elapsed.seconds)

    os.remove(lock_filename)