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
    cryptsy_mongo = CryptsyMongo(host="192.168.1.29")

    start_time = toCryptsyServerTime(datetime.utcnow() - timedelta(days=int(days)))

    print "Best markets:"
    tradeStats = cryptsy_mongo.getAllTradesFrom(start_time)
    filteredTradeStats = filter(
        lambda x: tradeStats[x]['Sell'] > tradeStats[x]['Fee'] + tradeStats[x]['Buy'] > 0 and tradeStats[x][
            'Buy'] > 0, tradeStats)
    sortedTradeStats = sorted(filteredTradeStats, key=lambda x: tradeStats[x]['Sell'] - tradeStats[x]['Buy'],
                              reverse=True)

    for tradeStat in sortedTradeStats:
        print "MarketId: {}, Sell: {}, Buy: {}, Earn: {}".format(tradeStat,
                                                                 tradeStats[tradeStat]['Sell'],
                                                                 tradeStats[tradeStat]['Buy'],
                                                                 tradeStats[tradeStat]['Sell'] - tradeStats[tradeStat][
                                                                     'Buy'])

    print "Worst markets:"
    tradeStats = cryptsy_mongo.getAllTradesFrom(start_time)
    filteredTradeStats = filter(
        lambda x: 0 < tradeStats[x]['Sell'] < tradeStats[x]['Fee'] + tradeStats[x]['Buy'] and tradeStats[x][
            'Buy'] > 0, tradeStats)
    sortedTradeStats = sorted(filteredTradeStats, key=lambda x: tradeStats[x]['Sell'] - tradeStats[x]['Buy'])

    for tradeStat in sortedTradeStats:
        print "MarketId: {}, Sell: {}, Buy: {}, Fee: {}, Earn: {}".format(tradeStat,
                                                                          tradeStats[tradeStat]['Sell'],
                                                                          tradeStats[tradeStat]['Buy'],
                                                                          tradeStats[tradeStat]['Fee'],
                                                                          tradeStats[tradeStat]['Sell'] -
                                                                          tradeStats[tradeStat]['Buy'],
                                                                          tradeStats[tradeStat]['Fee'])


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