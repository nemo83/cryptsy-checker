import getopt
import sys

from CryptsyPy import CryptsyPy


public = ''
private = ''

cryptsyclient = None


def main(argv):
    global public
    global private

    getEnv(argv)

    global cryptsyclient
    cryptsyclient = CryptsyPy(public, private)

    tradeStats = cryptsyclient.getAllTradesInTheLast(3)

    print "Best markets:"
    filteredTradeStats = filter(lambda x: tradeStats[x]['Sell'] > tradeStats[x]['Buy'] > 0, tradeStats)
    sortedTradeStats = sorted(filteredTradeStats, key=lambda x: tradeStats[x]['Sell'] - tradeStats[x]['Buy'],
                              reverse=True)
    for tradeStat in sortedTradeStats:
        print "MarketId: {}, Sell: {}, Buy: {}, Earn: {}".format(tradeStat,
                                                                 tradeStats[tradeStat]['Sell'],
                                                                 tradeStats[tradeStat]['Buy'],
                                                                 tradeStats[tradeStat]['Sell'] - tradeStats[tradeStat][
                                                                     'Buy'])

    print "Best markets (Fee Inc):"
    filteredTradeStats = filter(
        lambda x: tradeStats[x]['Sell'] > (tradeStats[x]['Buy'] + tradeStats[x]['Fee']) > 0 and tradeStats[x][
            'Buy'] > 0,
        tradeStats)
    sortedTradeStats = sorted(filteredTradeStats, key=lambda x: tradeStats[x]['Sell'] - tradeStats[x]['Buy'],
                              reverse=True)
    for tradeStat in sortedTradeStats:
        print "MarketId: {}, Sell: {}, Buy: {}, Fee: {}, Earn: {}".format(tradeStat,
                                                                          tradeStats[tradeStat]['Sell'],
                                                                          tradeStats[tradeStat]['Buy'],
                                                                          tradeStats[tradeStat]['Fee'],
                                                                          tradeStats[tradeStat]['Sell'] -
                                                                          tradeStats[tradeStat][
                                                                              'Buy'] - tradeStats[tradeStat]['Fee'])

    print "\nWorst markets:"
    filteredTradeStats = filter(lambda x: 0 < tradeStats[x]['Sell'] < tradeStats[x]['Buy'], tradeStats)
    sortedTradeStats = sorted(filteredTradeStats, key=lambda x: tradeStats[x]['Sell'] - tradeStats[x]['Buy'])
    for tradeStat in sortedTradeStats:
        print "MarketId: {}, Sell: {}, Buy: {}, Earn: {}".format(tradeStat,
                                                                 tradeStats[tradeStat]['Sell'],
                                                                 tradeStats[tradeStat]['Buy'],
                                                                 tradeStats[tradeStat]['Sell'] - tradeStats[tradeStat][
                                                                     'Buy'])

    print "\nWorst markets (Fee Inc):"
    filteredTradeStats = filter(lambda x: 0 < tradeStats[x]['Sell'] < (tradeStats[x]['Buy'] + tradeStats[x]['Fee']),
                                tradeStats)
    sortedTradeStats = sorted(filteredTradeStats, key=lambda x: tradeStats[x]['Sell'] - tradeStats[x]['Buy'])
    for tradeStat in sortedTradeStats:
        print "MarketId: {}, Sell: {}, Buy: {}, Fee: {}, Earn: {}".format(tradeStat,
                                                                          tradeStats[tradeStat]['Sell'],
                                                                          tradeStats[tradeStat]['Buy'],
                                                                          tradeStats[tradeStat]['Fee'],
                                                                          tradeStats[tradeStat]['Sell'] -
                                                                          tradeStats[tradeStat][
                                                                              'Buy'], tradeStats[tradeStat]['Fee'])


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