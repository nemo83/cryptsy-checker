from datetime import timedelta, datetime
import getopt
import sys
import os
import logging
from time import sleep

from pymongo import MongoClient

from CryptsyPy import CryptsyPy, toEightDigit, fromCryptsyServerTime, toCryptsyServerTime, CRYPTSY_HOURS_DIFFERENCE
from CryptsyMongo import CryptsyMongo




# create logger
logger = logging.getLogger("bot_logger")
logger.setLevel(logging.DEBUG)

# create console handler and set level to debug
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)

# create formatter
formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

# add formatter to ch
ch.setFormatter(formatter)

# add ch to logger
logger.addHandler(ch)

FEE = 0.0025
BASE_STAKE = 0.0005
TEST_STAKE = 0.00025
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


def normalizeValues(values):
    def normalize(value, min, scalingFactor):
        return (value - min) / scalingFactor if scalingFactor != 0 else (value - min)

    minValue = min(values)
    scalingFactor = max(values) - minValue
    normalizedValues = [normalize(value, minValue, scalingFactor) for value in values]
    return normalizedValues, minValue, scalingFactor


def calculateQuantity(amountToInvest, fee, buyPrice):
    return (amountToInvest - amountToInvest * fee) / buyPrice


def getMarketTrends(inactiveBtcMarkets, markets):
    recent_market_trends = cryptsy_mongo.getRecentMarketTrends()

    recent_market_trend_names = [recent_market_trend.marketName for recent_market_trend in recent_market_trends]

    inactive_recent_market_trend_names = filter(lambda x: x in inactiveBtcMarkets, recent_market_trend_names)

    market_trends = filter(lambda x: x.marketName in inactiveBtcMarkets and x.num_samples >= 200, recent_market_trends)

    for marketName in inactiveBtcMarkets:
        if marketName not in inactive_recent_market_trend_names:
            market_trend = cryptsy_mongo.calculateMarketTrend(marketName, markets[marketName])
            cryptsy_mongo.persistMarketTrend(market_trend)

            if market_trend.num_samples >= 200:
                market_trends.append(market_trend)

    marketIds = [int(market_trend.marketId) for market_trend in market_trends]

    return market_trends, marketIds


def investBTC(btcBalance, active_markets, markets):
    market_names = [market for market in markets]

    btcMarketNames = filter(lambda x: 'BTC' in x and 'Points' not in x, market_names)

    logger.info("activeMarkets: {}".format(active_markets))

    inactive_btc_markets = filter(lambda x: int(markets[x]) not in active_markets, btcMarketNames)

    logger.info("inactive_btc_markets: {}".format(
        [int(markets[inactive_btc_market]) for inactive_btc_market in inactive_btc_markets]))

    market_trends, marketIds = getMarketTrends(inactive_btc_markets, markets)

    sorted_market_trends = sorted(market_trends, key=lambda x: abs(0.0 - x.m))

    sorted_market_trend_ids = [x.marketId for x in sorted_market_trends]

    logger.info("sorted_market_trend_ids: {}".format(sorted_market_trend_ids))

    avg_filtered_market_trends = filter(lambda x: x.m != 0.0 and x.m >= -0.3 and x.avg >= 0.000001,
                                        sorted_market_trends)

    avg_filtered_market_trends_ids = [x.marketId for x in avg_filtered_market_trends]

    logger.info("avg_filtered_market_trends_ids: {}".format(avg_filtered_market_trends_ids))

    sorted_market_trends_to_bet_on = filter(lambda x: x.std > 2 * (x.avg * FEE), avg_filtered_market_trends)

    sorted_market_trends_to_bet_on_ids = [x.marketId for x in sorted_market_trends_to_bet_on]

    logger.info("sorted_market_trends_to_bet_on_ids: {}".format(sorted_market_trends_to_bet_on_ids))

    best_markets_last_24h = cryptsy_mongo.getBestPerformingMarketsFrom(
        toCryptsyServerTime(datetime.utcnow() - timedelta(hours=24)))

    logger.info("best_markets_last_24h: {}".format(best_markets_last_24h))

    worst_markets_last_6h = cryptsy_mongo.getWorstPerformingMarketsFrom(
        toCryptsyServerTime(datetime.utcnow() - timedelta(hours=6)))

    logger.info("worst_markets_last_6h: {}".format(worst_markets_last_6h))

    worst_markets_last_24h = cryptsy_mongo.getWorstPerformingMarketsFrom(
        toCryptsyServerTime(datetime.utcnow() - timedelta(hours=24)))

    logger.info("worst_markets_last_24h: {}".format(worst_markets_last_24h))

    worst_performing_markets = [int(market_id) for market_id in set(worst_markets_last_6h + worst_markets_last_24h)]

    logger.info("worst_performing_markets: {}".format(worst_performing_markets))

    best_performing_markets = [int(market) for market in best_markets_last_24h if
                               int(market) not in worst_performing_markets]

    logger.info("best_performing_markets: {}".format(best_performing_markets))

    logger.info("marketIds: {}".format(marketIds))

    suggested_market_ids = filter(lambda x: x in marketIds, userMarketIds) + filter(lambda x: x in marketIds,
                                                                                    best_performing_markets)

    suggested_market_trends = []

    for market_id in suggested_market_ids:
        for market_trend in market_trends:
            if int(market_trend.marketId) == market_id:
                suggested_market_trends.append(market_trend)

    other_sorted_market_trends = filter(
        lambda x: int(x.marketId) not in suggested_market_ids and int(x.marketId) not in worst_performing_markets,
        sorted_market_trends_to_bet_on)

    marketTrendsToInvestOn = suggested_market_trends + other_sorted_market_trends

    for market_trend in marketTrendsToInvestOn:

        if btcBalance < MINIMUM_AMOUNT_TO_INVEST:
            break

        if market_trend.marketId in userMarketIds:
            desiredAmountToInvest = TEST_STAKE
        elif market_trend.marketId in best_performing_markets[:3]:
            desiredAmountToInvest = BASE_STAKE * 6
        elif market_trend.marketId in best_performing_markets[3:6]:
            desiredAmountToInvest = BASE_STAKE * 3
        elif market_trend.marketId in best_performing_markets[6:]:
            desiredAmountToInvest = BASE_STAKE * 2
        else:
            desiredAmountToInvest = TEST_STAKE

        amountToInvest = min(desiredAmountToInvest, btcBalance)

        buy_market_trend = getMarketTrendFor(market_trend.marketName, market_trend.marketId, 6)

        if buy_market_trend.m == 0.0 or buy_market_trend.m <= -0.3 or buy_market_trend.num_samples < 20:
            logger.info(
                "Market {} has m: {} and number samples: {}".format(buy_market_trend.marketName, buy_market_trend.m,
                                                                    buy_market_trend.num_samples))
            continue

        buyPrice = getBuyPrice(buy_market_trend)

        quantity = calculateQuantity(amountToInvest, FEE, buyPrice)

        if buyPrice <= 0.0 or quantity <= 0.0:
            logger.info("Attempting to buy: {} {}, at price: {} - Order will not be placed.".format(quantity,
                                                                                                    market_trend.marketName,
                                                                                                    buyPrice))
            continue

        responseBody, apiCallSucceded = cryptsyClient.placeBuyOrder(market_trend.marketId, quantity, buyPrice)
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
    mongoClient = MongoClient(host="192.168.1.29")
    # mongoClient = MongoClient()
    mongoCryptsyDb = mongoClient.cryptsy_database
    mongoMarketsCollection = mongoCryptsyDb.markets_collection

    cryptsy_mongo = CryptsyMongo(host="192.168.1.29")
    # cryptsy_mongo = CryptsyMongo()


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
                logger.info(
                    "Cancelling order for {} market. Old Price: {}, New Price: {}".format(market_name, openOrder[4],
                                                                                          sellPrice))
                ordersToBeCancelled.append(openOrder[1])
            else:
                logger.info("Sell order expired but not deleted for {} market. Old Price: {}, New Price: {}".format(
                    market_name, openOrder[4], sellPrice))
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
        logger.info("No sell order for market {} will be placed. Not enough sale info.".format(marketName))
        return

    sell_price = getSellPrice(market_trend)

    if quantity * sell_price >= 0.00000010:
        cryptsyClient.placeSellOrder(market_trend.marketId, quantity, sell_price)
    else:
        logger.info("Order is less than 0.00000010: {}".format(quantity * sell_price))


def cancelOrders(ordersToBeCancelled):
    for orderToBeCancelled in ordersToBeCancelled:
        cryptsyClient.cancelOrder(orderToBeCancelled)
    if len(ordersToBeCancelled) > 0:
        sleep(5)


def updateTradeHistory():
    recent_trades = cryptsyClient.getRecentTrades()
    if recent_trades is not None:
        cryptsy_mongo.persistTrades(recent_trades)


def main(argv):
    getEnv(argv)

    initCryptsyClient()

    initMongoClient()

    updateTradeHistory()

    markets = cryptsyClient.getMarkets()

    ordersToBeCancelled = getOrdersToBeCancelled(markets)

    cancelOrders(ordersToBeCancelled)

    balanceList = filter(lambda x: x[0] != 'Points', cryptsyClient.getInfo())
    logger.info("Current Balance:")
    for balance in balanceList:
        logger.info("{}, {}".format(balance[0], balance[1]))

    btcBalance = 0.0
    for balance in balanceList:
        if balance[0] == 'BTC':
            btcBalance = balance[1]
        else:
            marketName = "{}/BTC".format(balance[0])
            marketId = markets[marketName]
            placeSellOrder(marketName, marketId, balance[1])

    sleep(5)

    active_markets = set([int(active_order[0]) for active_order in cryptsyClient.getAllActiveOrders()])

    if sell_only:
        logger.info("Sell only flag active. No buy trade will be open. Returning...")
    elif btcBalance >= MINIMUM_AMOUNT_TO_INVEST:
        investBTC(btcBalance, active_markets, markets)
    else:
        logger.info("Not enough funds. Exiting")

    logger.info("Complete")


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
    logger.info("Started")
    lock_filename = "bot.lock"
    if os.path.isfile(lock_filename):
        logger.info("Bot already running. Exiting...")
        sys.exit(0)

    lock_file = open(lock_filename, "w+")
    lock_file.close()

    try:
        main(sys.argv[1:])
    except Exception, ex:
        logger.exception("Unexpected error: {}".format(sys.exc_info()[0]))

    logger.info("Finished")
    os.remove(lock_filename)