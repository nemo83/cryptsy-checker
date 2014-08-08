import getopt
import sys
from datetime import datetime, timedelta

from CryptsyPy import CryptsyPy, toCryptsyServerTime
from CryptsyMongo import CryptsyMongo


public = ''
private = ''
days = 1

cryptsy_client = None


def main(argv):
    global public
    global private

    getEnv(argv)

    global cryptsy_client
    cryptsy_client = CryptsyPy(public, private)
    # cryptsy_mongo = CryptsyMongo(host="192.168.1.29")
    cryptsy_mongo = CryptsyMongo()

    recent_trades = cryptsy_client.getRecentTrades()
    if recent_trades is not None:
        cryptsy_mongo.persistTrades(recent_trades)

    start_time = toCryptsyServerTime(datetime.utcnow() - timedelta(days=int(days)))

    print "Best markets:"
    mongotradeStats = cryptsy_mongo.getAllTradesFrom(start_time)
    filteredTradeStats = filter(
        lambda x: mongotradeStats[x]['Sell'] >= mongotradeStats[x]['Fee'] + mongotradeStats[x]['Buy'],
        mongotradeStats)
    sortedTradeStats = sorted(filteredTradeStats, key=lambda x: mongotradeStats[x]['Sell'] - mongotradeStats[x]['Buy'],
                              reverse=True)

    for tradeStat in sortedTradeStats:
        print "MarketId: {}, Sell: {}, Buy: {}, Earn: {}".format(tradeStat,
                                                                 mongotradeStats[tradeStat]['Sell'],
                                                                 mongotradeStats[tradeStat]['Buy'],
                                                                 mongotradeStats[tradeStat]['Sell'] -
                                                                 mongotradeStats[tradeStat][
                                                                     'Buy'])

    print "Worst markets:"
    mongotradeStats = cryptsy_mongo.getAllTradesFrom(start_time)
    filteredTradeStats = filter(
        lambda x: 0 < mongotradeStats[x]['Sell'] < mongotradeStats[x]['Fee'] + mongotradeStats[x]['Buy'],
        mongotradeStats)
    sortedTradeStats = sorted(filteredTradeStats, key=lambda x: mongotradeStats[x]['Sell'] - mongotradeStats[x]['Buy'])

    for tradeStat in sortedTradeStats:
        print "MarketId: {}, Sell: {}, Buy: {}, Fee: {}, Earn: {}".format(tradeStat,
                                                                          mongotradeStats[tradeStat]['Sell'],
                                                                          mongotradeStats[tradeStat]['Buy'],
                                                                          mongotradeStats[tradeStat]['Fee'],
                                                                          mongotradeStats[tradeStat]['Sell'] -
                                                                          mongotradeStats[tradeStat]['Buy'],
                                                                          mongotradeStats[tradeStat]['Fee'])


def getEnv(argv):
    global public
    global private
    global days
    try:
        opts, args = getopt.getopt(argv, "d:h", ["help", "public=", "private="])
    except getopt.GetoptError:
        sys.exit(2)
    for opt, arg in opts:
        if opt in ("-h", "--help"):
            sys.exit()
        elif opt == "--public":
            public = arg
        elif opt == "--private":
            private = arg
        elif opt == "-d":
            days = arg


if __name__ == "__main__":
    main(sys.argv[1:])