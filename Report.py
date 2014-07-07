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

    tradeStats = cryptsyclient.getAllTradesInTheLast(2)
    print tradeStats
    filteredTradeStats = filter(lambda x: tradeStats[x]['Sell'] > tradeStats[x]['Buy'] > 0, tradeStats)
    sortedTradeStats = sorted(filteredTradeStats, key=lambda x: tradeStats[x]['Sell'] - tradeStats[x]['Buy'],
                              reverse=True)

    print "Best markets:"
    for tradeStat in sortedTradeStats:
        print "MarketId: {}, Sell: {}, Buy: {}, Earn: {}".format(tradeStat,
                                                                 tradeStats[tradeStat]['Sell'],
                                                                 tradeStats[tradeStat]['Buy'],
                                                                 tradeStats[tradeStat]['Sell'] - tradeStats[tradeStat][
                                                                     'Buy'])



    print "\nWorst markets:"
    filteredTradeStats = filter(lambda x: 0 < tradeStats[x]['Sell'] < tradeStats[x]['Buy'], tradeStats)
    sortedTradeStats = sorted(filteredTradeStats, key=lambda x: tradeStats[x]['Sell'] - tradeStats[x]['Buy'])
    for tradeStat in sortedTradeStats:
        print "MarketId: {}, Sell: {}, Buy: {}, Earn: {}".format(tradeStat,
                                                                 tradeStats[tradeStat]['Sell'],
                                                                 tradeStats[tradeStat]['Buy'],
                                                                 tradeStats[tradeStat]['Sell'] - tradeStats[tradeStat][
                                                                     'Buy'])


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