from datetime import timedelta, datetime
import getopt
import sys
import os
from time import sleep

from pymongo import MongoClient

from CryptsyPy import CryptsyPy, toEightDigit, fromCryptsyServerTime, toCryptsyServerTime, CRYPTSY_HOURS_DIFFERENCE
from CryptsyMongo import CryptsyMongo


FEE = 0.0025
BASE_STAKE = 0.0005
MINIMUM_AMOUNT_TO_INVEST = 0.0005

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
    recent_market_trends = cryptsy_mongo.getRecentMarketTrends()

    recent_market_trend_names = [recent_market_trend.marketName for recent_market_trend in recent_market_trends]

    inactive_recent_market_trend_names = filter(lambda x: x in filteredBtcMarkets, recent_market_trend_names)

    market_trends = filter(lambda x: x.marketName in filteredBtcMarkets, recent_market_trends)

    for marketName in filteredBtcMarkets:
        if marketName not in inactive_recent_market_trend_names:
            market_trend = cryptsy_mongo.calculateMarketTrend(marketName, markets[marketName])
            cryptsy_mongo.persistMarketTrend(market_trend)

            if market_trend.num_samples >= 100:
                market_trends.append(market_trend)

    marketIds = [market_trend.marketId for market_trend in market_trends]

    return market_trends, marketIds


def investBTC(btcBalance, activeMarkets, markets):
    market_names = [market for market in markets]

    btcMarketNames = filter(lambda x: 'BTC' in x and 'Points' not in x, market_names)

    inactiveBtcMarkets = filter(lambda x: markets[x] not in activeMarkets, btcMarketNames)

    marketTrends, marketIds = getMarketTrends(inactiveBtcMarkets, markets)

    sortedMarketTrends = filter(lambda x: x.m != 0.0 and x.avg >= 0.0000002 and x.std > 4 * (x.avg * FEE),
                                sorted(marketTrends, key=lambda x: abs(0.0 - x.m)))

    bestPerformingMarkets = cryptsyClient.getBestPerformingMarketsFeeIncluded()

    worstPerformingMarkets = cryptsyClient.getWorstPerformingMarketsFeeIncluded()

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
        elif marketTrend.marketId in bestPerformingMarkets[:3]:
            desiredAmountToInvest = BASE_STAKE * 6
        elif marketTrend.marketId in bestPerformingMarkets[3:6]:
            desiredAmountToInvest = BASE_STAKE * 3
        elif marketTrend.marketId in bestPerformingMarkets[6:10]:
            desiredAmountToInvest = BASE_STAKE * 2
        elif marketTrend.marketId in bestPerformingMarkets[10:]:
            desiredAmountToInvest = BASE_STAKE * 1
        else:
            desiredAmountToInvest = BASE_STAKE

        amountToInvest = min(desiredAmountToInvest, btcBalance)

        buy_market_trend = getMarketTrendFor(marketTrend.marketName, marketTrend.marketId, 6)

        if buy_market_trend.m == 0.0 or buy_market_trend.num_samples < 50:
            print "Market {} has m: {} and number samples: {}".format(buy_market_trend.marketName, buy_market_trend.m,
                                                                      buy_market_trend.num_samples)
            continue

        buyPrice = getBuyPrice(buy_market_trend)

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


def getMarketTrendFor(marketName, marketId, lastXHours):
    return cryptsy_mongo.calculateMarketTrend(market_name=marketName,
                                              market_id=marketId,
                                              interval=timedelta(hours=CRYPTSY_HOURS_DIFFERENCE + lastXHours))


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


def getOrdersToBeCancelled(markets):
    allActiveOrders = cryptsyClient.getAllActiveOrders()
    ordersToBeCancelled = []
    for openOrder in allActiveOrders:
        openMarketNormalized = fromCryptsyServerTime(datetime.strptime(openOrder[2], '%Y-%m-%d %H:%M:%S'))
        if openOrder[3] == 'Buy' and (openMarketNormalized + timedelta(minutes=30)) < datetime.utcnow():
            ordersToBeCancelled.append(openOrder[1])
        elif openOrder[3] == 'Sell' and (openMarketNormalized + timedelta(minutes=90)) < datetime.utcnow():

            market_name = next((market_name for market_name in markets if (markets[market_name] == openOrder[0])), None)

            market_trend = getMarketTrendFor(market_name, openOrder[0], 6)

            sellPrice = toEightDigit(getSellPrice(market_trend))

            if float(sellPrice) != float(openOrder[4]):
                print "Cancelling order for {} market. Old Price: {}, New Price: {}".format(market_name, openOrder[4],
                                                                                            sellPrice)
                ordersToBeCancelled.append(openOrder[1])
            else:
                print "Sell order expired but not deleted for {} market. Old Price: {}, New Price: {}".format(
                    market_name, openOrder[4], sellPrice)
    return ordersToBeCancelled


def getNormalizedEstimatedPrice(market_trend):
    timeX = (toCryptsyServerTime(datetime.utcnow()) - epoch).total_seconds()
    estimatedPrice = estimateValue(timeX,
                                   market_trend.m, market_trend.n,
                                   market_trend.minX, market_trend.scalingFactorX,
                                   market_trend.minY, market_trend.scalingFactorY)
    normalizedEstimatedPrice = float(estimatedPrice) / 100000000
    return normalizedEstimatedPrice


def getBuyPrice(market_trend):
    normalizedEstimatedPrice = getNormalizedEstimatedPrice(market_trend)
    return normalizedEstimatedPrice - market_trend.std


def getSellPrice(market_trend):
    normalizedEstimatedPrice = getNormalizedEstimatedPrice(market_trend)
    return normalizedEstimatedPrice + market_trend.std


def placeSellOrder(marketName, marketId, quantity):
    market_trend = getMarketTrendFor(marketName, marketId, 6)
    if market_trend.m == 0.0:
        print "No sell order for market {} will be placed. Not enough sale info.".format(marketName)
        return

    sell_price = getSellPrice(market_trend)

    if quantity * sell_price >= 0.00000010:
        cryptsyClient.placeSellOrder(market_trend.marketId, quantity, sell_price)
    else:
        print "Order is less than 0.00000010: {}".format(quantity * sell_price)


def cancelOrders(ordersToBeCancelled):
    for orderToBeCancelled in ordersToBeCancelled:
        cryptsyClient.cancelOrder(orderToBeCancelled)
    if len(ordersToBeCancelled) > 0:
        sleep(5)


def main(argv):
    getEnv(argv)

    initCryptsyClient()

    initMongoClient()

    markets = cryptsyClient.getMarkets()

    ordersToBeCancelled = getOrdersToBeCancelled(markets)

    cancelOrders(ordersToBeCancelled)

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

    sleep(5)

    activeMarkets = set([active_order[0] for active_order in cryptsyClient.getAllActiveOrders()])

    if sell_only:
        print "Sell only flag active. No buy trade will be open. Returning..."
    elif True: #btcBalance >= MINIMUM_AMOUNT_TO_INVEST:
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
    starttime = datetime.utcnow()
    print "Started at {}".format(starttime)
    lock_filename = "bot.lock"
    if os.path.isfile(lock_filename):
        print "Bot already running. Exiting..."
        sys.exit(0)

    lock_file = open(lock_filename, "w+")
    lock_file.close()

    try:
        main(sys.argv[1:])
    except Exception, err:
        print "Unexpected error: {}".format(sys.exc_info()[0])
        print err

    elapsed = datetime.utcnow() - starttime

    print "Finished at {}".format(datetime.utcnow())
    print "Execution took: {}".format(elapsed.seconds)

    os.remove(lock_filename)