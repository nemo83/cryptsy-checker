import getopt
import sys
from datetime import datetime, timedelta

from CryptsyPy import CryptsyPy, toCryptsyServerTime, toEightDigit
from CryptsyMongo import CryptsyMongo


public = ''
private = ''
hours = 12

cryptsy_client = None


def main(argv):
    global public
    global private

    getEnv(argv)

    global cryptsy_client
    cryptsy_client = CryptsyPy(public, private)
    # cryptsy_mongo = CryptsyMongo(host="192.168.1.29")
    cryptsy_mongo = CryptsyMongo()

    recent_market_trends = cryptsy_mongo.getRecentMarketTrends()

    recent_trades = cryptsy_client.getRecentTrades()
    if recent_trades is not None:
        cryptsy_mongo.persistTrades(recent_trades)

    start_time = toCryptsyServerTime(datetime.utcnow() - timedelta(hours=int(hours)))

    total_buy_best = 0.0
    total_sell_best = 0.0
    total_fee_best = 0.0
    print "Best markets:"
    mongotradeStats = cryptsy_mongo.getAllTradesFrom(start_time)
    filteredTradeStats = filter(
        lambda x: mongotradeStats[x]['Sell'] >= mongotradeStats[x]['Fee'] + mongotradeStats[x]['Buy'],
        mongotradeStats)
    sortedTradeStats = sorted(filteredTradeStats, key=lambda x: mongotradeStats[x]['Sell'] - mongotradeStats[x]['Buy'],
                              reverse=True)

    for tradeStat in sortedTradeStats:
        total_buy_best += float(mongotradeStats[tradeStat]['Buy'])
        total_sell_best += float(mongotradeStats[tradeStat]['Sell'])
        total_fee_best += float(mongotradeStats[tradeStat]['Fee'])
        print "MarketId: {}, Std:{}, Sell: {}, Buy: {}, Earn: {}".format(tradeStat,
                                                                         next((toEightDigit(market_trend.std) for
                                                                               market_trend in recent_market_trends if
                                                                               int(market_trend.marketId) == int(
                                                                                   tradeStat)), None),
                                                                         toEightDigit(
                                                                             mongotradeStats[tradeStat]['Sell']),
                                                                         toEightDigit(
                                                                             mongotradeStats[tradeStat]['Buy']),
                                                                         toEightDigit(
                                                                             mongotradeStats[tradeStat]['Sell'] -
                                                                             mongotradeStats[tradeStat][
                                                                                 'Buy']))

    print "Best markets total: buy: {}, sell: {}, fee:{} - earnings: {}".format(total_buy_best, total_sell_best,
                                                                                total_fee_best,
                                                                                total_sell_best - total_buy_best - total_fee_best)

    total_buy_worst = 0.0
    total_sell_worst = 0.0
    total_fee_worst = 0.0
    print "Worst markets:"
    mongotradeStats = cryptsy_mongo.getAllTradesFrom(start_time)
    filteredTradeStats = filter(
        lambda x: 0 < mongotradeStats[x]['Sell'] < mongotradeStats[x]['Fee'] + mongotradeStats[x]['Buy'],
        mongotradeStats)
    sortedTradeStats = sorted(filteredTradeStats, key=lambda x: mongotradeStats[x]['Sell'] - mongotradeStats[x]['Buy'])

    for tradeStat in sortedTradeStats:
        total_buy_worst += float(mongotradeStats[tradeStat]['Buy'])
        total_sell_worst += float(mongotradeStats[tradeStat]['Sell'])
        total_fee_worst += float(mongotradeStats[tradeStat]['Fee'])
        print "MarketId: {}, Std:{}, Sell: {}, Buy: {}, Fee: {}, Earn: {}".format(tradeStat,
                                                                                  next((toEightDigit(market_trend.std)
                                                                                        for market_trend in
                                                                                        recent_market_trends if int(
                                                                                      market_trend.marketId) == int(
                                                                                      tradeStat)), None),
                                                                                  toEightDigit(
                                                                                      mongotradeStats[tradeStat][
                                                                                          'Sell']),
                                                                                  toEightDigit(
                                                                                      mongotradeStats[tradeStat][
                                                                                          'Buy']),
                                                                                  toEightDigit(
                                                                                      mongotradeStats[tradeStat][
                                                                                          'Fee']),
                                                                                  toEightDigit(
                                                                                      mongotradeStats[tradeStat][
                                                                                          'Sell'] -
                                                                                      mongotradeStats[tradeStat]['Buy'],
                                                                                      mongotradeStats[tradeStat][
                                                                                          'Fee']))

    print "Worst markets total: buy: {}, sell: {}, fee:{} - earnings: {}".format(total_buy_worst, total_sell_worst,
                                                                                 total_fee_worst,
                                                                                 total_sell_worst - total_buy_worst - total_fee_worst)

    print "Total stats: total earning: {}".format(
        (total_sell_best + total_sell_worst) - (total_buy_best + total_buy_worst + total_fee_best + total_fee_worst))


def getEnv(argv):
    global public
    global private
    global hours
    try:
        opts, args = getopt.getopt(argv, "h", ["help", "public=", "private=", "hours="])
    except getopt.GetoptError:
        sys.exit(2)
    for opt, arg in opts:
        if opt in ("-h", "--help"):
            sys.exit()
        elif opt == "--public":
            public = arg
        elif opt == "--private":
            private = arg
        elif opt == "--hours":
            hours = arg


if __name__ == "__main__":
    main(sys.argv[1:])