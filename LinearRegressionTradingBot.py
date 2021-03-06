from datetime import timedelta, datetime
import getopt
import sys
import os
import logging
from time import sleep

from pymongo import MongoClient

from CryptsyPy import CryptsyPy, fromCryptsyServerTime, toCryptsyServerTime, CRYPTSY_HOURS_DIFFERENCE, toEightDigit
from CryptsyMongo import CryptsyMongo
















# create logger
logger = logging.getLogger("bot_logger")
logger.setLevel(logging.INFO)

# create console handler and set level to debug
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)

# create formatter
formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

# add formatter to ch
ch.setFormatter(formatter)

# add ch to logger
logger.addHandler(ch)

FEE = 0.0025
BASE_STAKE = 0.0005
TEST_STAKE = 0.000001
MINIMUM_AMOUNT_TO_INVEST = 0.000001

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

    for recent_market_trend in recent_market_trends:
        if recent_market_trend.std < 0.0:
            logger.warn(
                "Non positive standard deviation {} for recent market trend, market {} ".format(recent_market_trend.std,
                                                                                                recent_market_trend.marketName))

    recent_market_trend_names = [recent_market_trend.marketName for recent_market_trend in recent_market_trends]

    inactive_recent_market_trend_names = filter(lambda x: x in inactiveBtcMarkets, recent_market_trend_names)

    market_trends = filter(lambda x: x.marketName in inactiveBtcMarkets and x.num_samples >= 25, recent_market_trends)

    for marketName in inactiveBtcMarkets:
        if marketName not in inactive_recent_market_trend_names:
            market_trend = cryptsy_mongo.calculateMarketTrend(marketName, markets[marketName],
                                                              interval=timedelta(hours=CRYPTSY_HOURS_DIFFERENCE + 3))
            if market_trend.std < 0:
                logger.warn("Non positive standard deviation {} for market {}".format(market_trend.std,
                                                                                      market_trend.marketName))
            cryptsy_mongo.persistMarketTrend(market_trend)

            if market_trend.num_samples >= 25:
                market_trends.append(market_trend)

    marketIds = [int(market_trend.marketId) for market_trend in market_trends]

    return market_trends, marketIds


def priceVariation(price, fee_multiplier=1, percent_value=0.0):
    return fee_multiplier * price * FEE + price * (float(percent_value) / float(100))


def investBTC(btcBalance, active_markets, markets):
    market_names = [market for market in markets]

    btcMarketNames = filter(lambda x: 'BTC' in x and 'Points' not in x, market_names)

    logger.debug("activeMarkets: {}".format(active_markets))

    inactive_btc_markets = filter(lambda x: int(markets[x]) not in active_markets, btcMarketNames)

    logger.debug("inactive_btc_markets: {}".format(
        [int(markets[inactive_btc_market]) for inactive_btc_market in inactive_btc_markets]))

    market_trends, marketIds = getMarketTrends(inactive_btc_markets, markets)

    sorted_market_trends = sorted(market_trends, key=lambda x: abs(0.0 - x.m))

    sorted_market_trend_ids = [x.marketId for x in sorted_market_trends]

    logger.info("sorted_market_trend_ids: {}".format(sorted_market_trend_ids))

    avg_filtered_market_trends = filter(lambda x: x.m != 0.0 and x.m >= -0.1 and x.avg >= 0.000001,
                                        sorted_market_trends)

    avg_filtered_market_trends_ids = [x.marketId for x in avg_filtered_market_trends]

    logger.debug("avg_filtered_market_trends_ids: {}".format(avg_filtered_market_trends_ids))

    # sorted_market_trends_to_bet_on = filter(lambda x: x.std > (x.avg * FEE + x.avg * DESIRED_EARNING),
    # avg_filtered_market_trends)

    # sorted_market_trends_to_bet_on = filter(lambda x: x.std > 2 * (x.avg * FEE), avg_filtered_market_trends)
    sorted_market_trends_to_bet_on = avg_filtered_market_trends

    sorted_market_trends_to_bet_on_ids = [x.marketId for x in sorted_market_trends_to_bet_on]

    logger.info("sorted_market_trends_to_bet_on_ids: {}".format(sorted_market_trends_to_bet_on_ids))

    best_markets_last_3h = cryptsy_mongo.getBestPerformingMarketsFrom(
        toCryptsyServerTime(datetime.utcnow() - timedelta(hours=3)))

    logger.debug("best_markets_last_3h: {}".format(best_markets_last_3h))

    worst_markets_last_30m = cryptsy_mongo.getWorstPerformingMarketsFrom(
        toCryptsyServerTime(datetime.utcnow() - timedelta(minutes=30)))

    logger.debug("worst_markets_last_30m: {}".format(worst_markets_last_30m))

    worst_performing_markets = [int(market_id) for market_id in set(worst_markets_last_30m)]

    logger.info("worst_performing_markets: {}".format(worst_performing_markets))

    best_performing_markets = [int(market) for market in best_markets_last_3h if
                               int(market) not in worst_performing_markets]

    logger.info("best_performing_markets: {}".format(best_performing_markets))

    logger.info("marketIds: {}".format(marketIds))

    logger.info("userMarketIds: {}".format(userMarketIds))

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

    market_multipliers = cryptsy_mongo.getMarketsMultipliers()

    logger.info("Buy - Markets Multiplier: {}".format(market_multipliers))

    for market_trend in marketTrendsToInvestOn:

        if btcBalance < MINIMUM_AMOUNT_TO_INVEST:
            break

        market_multiplier = market_multipliers[
            market_trend.marketId] if market_trend.marketId in market_multipliers else 0

        # logger.info(
        # "Buy - {}({}) multiplier: {}".format(market_trend.marketName, market_trend.marketId, market_multiplier))

        if int(market_trend.marketId) in userMarketIds:
            desiredAmountToInvest = TEST_STAKE
        elif market_multiplier > 0:
            desiredAmountToInvest = BASE_STAKE * market_multiplier
        elif market_multiplier == 0:
            desiredAmountToInvest = TEST_STAKE
        elif market_multiplier < 0:
            desiredAmountToInvest = TEST_STAKE
        else:
            desiredAmountToInvest = TEST_STAKE

        amountToInvest = min(desiredAmountToInvest, btcBalance)

        one_hour_trend = getMarketTrendFor(market_trend.marketName, market_trend.marketId, 1)

        two_hours_trend = getMarketTrendFor(market_trend.marketName, market_trend.marketId, 2)

        three_hours_trend = getMarketTrendFor(market_trend.marketName, market_trend.marketId, 3)

        if three_hours_trend.m == 0.0 or three_hours_trend.m < 0.0 or three_hours_trend.num_samples < 25:
            logger.info(
                "Buy - REJECTED - {}({}) has m: {} and number samples: {}".format(three_hours_trend.marketName,
                                                                                  three_hours_trend.marketId,
                                                                                  three_hours_trend.m,
                                                                                  three_hours_trend.num_samples))
            continue
        elif two_hours_trend.m > one_hour_trend.m < 0.3:
            logger.info(
                "Buy - REJECTED - {}({}) has 3h-2h-1h: {}, {}, {} ".format(three_hours_trend.marketName,
                                                                           three_hours_trend.marketId,
                                                                           three_hours_trend.m,
                                                                           two_hours_trend.m,
                                                                           one_hour_trend.m))
            continue

        buyPrice = getBuyPrice(three_hours_trend)

        quantity = calculateQuantity(amountToInvest, FEE, buyPrice)

        if buyPrice <= 0.0 or quantity <= 0.0:
            logger.info(
                "Buy - REJECTED - {}({}) quantity: {} price: {}.".format(market_trend.marketName, market_trend.marketId,
                                                                         quantity,
                                                                         toEightDigit(buyPrice)))
            continue

        logger.info(
            "Buy - PLACING - {}({}) quantity: {}, price: {}".format(three_hours_trend.marketName,
                                                                    three_hours_trend.marketId,
                                                                    quantity,
                                                                    toEightDigit(buyPrice)))

        responseBody, apiCallSucceded = cryptsyClient.placeBuyOrder(market_trend.marketId, quantity, buyPrice)
        if apiCallSucceded:
            btcBalance -= amountToInvest


def getMarketTrendFor(marketName, marketId, lastXHours):
    market_trend = cryptsy_mongo.calculateMarketTrend(market_name=marketName,
                                                      market_id=marketId,
                                                      interval=timedelta(hours=CRYPTSY_HOURS_DIFFERENCE + lastXHours))

    if market_trend.std < 0:
        logger.warn("Non positive standard deviation {} for market {} on a {} hours window".format(market_trend.std,
                                                                                                   market_trend.marketName,
                                                                                                   lastXHours))

    return market_trend


def initCryptsyClient():
    global cryptsyClient
    cryptsyClient = CryptsyPy(public, private)


def initMongoClient():
    global mongoClient, mongoCryptsyDb, mongoMarketsCollection, cryptsy_mongo
    mongoClient = MongoClient(host="192.168.1.33")
    # mongoClient = MongoClient()
    mongoCryptsyDb = mongoClient.cryptsy_database
    mongoMarketsCollection = mongoCryptsyDb.markets_collection

    cryptsy_mongo = CryptsyMongo(host="192.168.1.33")
    # cryptsy_mongo = CryptsyMongo()


def getOrdersToBeCancelled():
    allActiveOrders = cryptsyClient.getAllActiveOrders()
    ordersToBeCancelled = []
    for openOrder in allActiveOrders:
        openMarketNormalized = fromCryptsyServerTime(datetime.strptime(openOrder[2], '%Y-%m-%d %H:%M:%S'))
        if openOrder[3] == 'Buy' and (openMarketNormalized + timedelta(minutes=5)) < datetime.utcnow():
            ordersToBeCancelled.append(openOrder[1])
        elif openOrder[3] == 'Sell' and (openMarketNormalized + timedelta(minutes=10)) < datetime.utcnow():
            ordersToBeCancelled.append(openOrder[1])
    return ordersToBeCancelled


def getBuyPrice(market_trend):
    actual_estimated_price = cryptsy_mongo.getNormalizedEstimatedPrice(market_trend)
    std_buy_price = actual_estimated_price - market_trend.std

    if market_trend.m > 0.5:
        buy_price = actual_estimated_price - priceVariation(actual_estimated_price)
        logger.info("Buy - getBuyPrice - {}({}) - GROWING_TREND - buy_price: {}".format(market_trend.marketName,
                                                                                        market_trend.marketId,
                                                                                        toEightDigit(buy_price)))
    elif market_trend > -0.1:
        variation_buy_price = actual_estimated_price - priceVariation(actual_estimated_price, fee_multiplier=2,
                                                                      percent_value=0.5)
        buy_price = min(std_buy_price, variation_buy_price)
        logger.info("Buy - getBuyPrice - {}({}) - CONSTANT_TREND - buy_price: {}".format(market_trend.marketName,
                                                                                         market_trend.marketId,
                                                                                         toEightDigit(buy_price)))
    else:
        variation_buy_price = actual_estimated_price - priceVariation(actual_estimated_price, fee_multiplier=2,
                                                                      percent_value=max(1.5, abs(market_trend.m)))
        buy_price = min(std_buy_price, variation_buy_price)
        logger.info("Buy - getBuyPrice - {}({}) - DECREASING_TREND - buy_price: {}".format(market_trend.marketName,
                                                                                           market_trend.marketId,
                                                                                           toEightDigit(buy_price)))

    return buy_price


def getSellPrice(market_trend):
    actual_estimated_price = cryptsy_mongo.getNormalizedEstimatedPrice(market_trend)

    if market_trend.m > 0.5:
        last_buy_trade = next(cryptsy_mongo.getLastTradeFor(market_id=market_trend.marketId, trade_type="Buy"))
        trade_price = float(last_buy_trade['tradeprice'])
        sell_price = trade_price + priceVariation(price=trade_price, fee_multiplier=2, percent_value=1)
        logger.info("Sell - getSellPrice - {}({}) - GROWING_TREND - sell_price: {}".format(market_trend.marketName,
                                                                                           market_trend.marketId,
                                                                                           toEightDigit(sell_price)))
    elif market_trend > 0.0:
        last_buy_trade = next(cryptsy_mongo.getLastTradeFor(market_id=market_trend.marketId, trade_type="Buy"))
        trade_price = float(last_buy_trade['tradeprice'])
        sell_price = trade_price + priceVariation(price=trade_price, fee_multiplier=4, percent_value=0.25)
        logger.info("Sell - getSellPrice - {}({}) - CONSTANT_TREND - sell_price: {}".format(market_trend.marketName,
                                                                                           market_trend.marketId,
                                                                                           toEightDigit(sell_price)))
    else:
        sell_price = actual_estimated_price
        logger.info("Sell - getSellPrice - {}({}) - DECREASING_TREND - sell_price: {}".format(market_trend.marketName,
                                                                                              market_trend.marketId,
                                                                                              toEightDigit(sell_price)))

    return sell_price


def getEstimatedPrice(market_trend):
    return cryptsy_mongo.getNormalizedEstimatedPrice(market_trend)


def placeSellOrder(marketName, marketId, quantity):
    three_hours_trend = getMarketTrendFor(marketName, marketId, 3)

    sell_trend = three_hours_trend

    if sell_trend.m == 0.0:
        sell_trend = getMarketTrendFor(marketName, marketId, 12)

    if sell_trend.m == 0.0:
        logger.info("No sell order for market {} will be placed. Not enough sale info.".format(marketName))
        return

    sell_price = getSellPrice(sell_trend)

    if quantity * sell_price > 0.0000001025:
        cryptsyClient.placeSellOrder(three_hours_trend.marketId, quantity, sell_price)
    else:
        logger.info("Order is less than 0.00000010: {}".format(quantity * sell_price))


def cancelOrders(ordersToBeCancelled):
    for orderToBeCancelled in ordersToBeCancelled:
        cryptsyClient.cancelOrder(orderToBeCancelled)
    if len(ordersToBeCancelled) > 0:
        sleep(6)


def updateTradeHistory():
    recent_trades = cryptsyClient.getRecentTrades()
    if recent_trades is not None:
        cryptsy_mongo.persistTrades(recent_trades)


def main(argv):
    getEnv(argv)

    initCryptsyClient()

    initMongoClient()

    if not sell_only:
        updateTradeHistory()

    markets = cryptsyClient.getMarkets()

    ordersToBeCancelled = getOrdersToBeCancelled()

    cancelOrders(ordersToBeCancelled)

    balanceList = filter(lambda x: x[0] != 'Points', cryptsyClient.getInfo())
    # logger.info("Current Balance:")
    # for balance in balanceList:
    # logger.info("{}, {}".format(balance[0], balance[1]))

    btcBalance = 0.0
    sell_order_placed = False
    for balance in balanceList:
        if balance[0] == 'BTC':
            btcBalance = balance[1]
        else:
            marketName = "{}/BTC".format(balance[0])
            marketId = markets[marketName]
            placeSellOrder(marketName, marketId, balance[1])
            sell_order_placed = True

    if sell_order_placed:
        sleep(6)

    active_markets = set([2] + [int(active_order[0]) for active_order in cryptsyClient.getAllActiveOrders()])

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
            userMarketIds = [int(x) for x in arg.split(",")]
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
