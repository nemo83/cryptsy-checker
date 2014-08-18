from datetime import datetime, timedelta
import sys
import getopt

from CryptsyMongo import CryptsyMongo, epoch
from CryptsyPy import CryptsyPy, toCryptsyServerTime, toEightDigit


cryptsyClient = None

public = ''
private = ''
userMarketIds = []


def estimateValue(x, m, n, minX, scalingFactorX, minY, scalingFactorY):
    x_ = (float(x) - minX) / scalingFactorX
    y_ = x_ * m + n
    return y_ * scalingFactorY + minY


def getNormalizedEstimatedPrice(market_trend, time_x=datetime.utcnow()):
    timeX = (toCryptsyServerTime(time_x) - epoch).total_seconds()
    estimatedPrice = estimateValue(timeX,
                                   market_trend.m, market_trend.n,
                                   market_trend.minX, market_trend.scalingFactorX,
                                   market_trend.minY, market_trend.scalingFactorY)
    normalizedEstimatedPrice = float(estimatedPrice) / 100000000
    return normalizedEstimatedPrice


def trading_history(market_name, market_id):
    interval = timedelta(days=1, hours=4)

    cryptsy_mongo = CryptsyMongo(host="192.168.1.33")

    timeStart = datetime.utcnow() - interval
    trades = cryptsy_mongo.trades_collection.find(
        {"marketid": str(market_id), "datetime": {"$gt": timeStart.strftime("%Y-%m-%d %H:%M:%S")}}).sort('datetime', -1)

    for trade in trades:
        print "{}({}) {} - {} at {}".format(market_name, market_id,
                                           datetime.strptime(trade['datetime'], '%Y-%m-%d %H:%M:%S'),
                                           toEightDigit(float(trade['tradeprice'])), trade['tradetype'])


def main(argv):
    getEnv(argv)

    cryptsy_py = CryptsyPy(public=public, private=private)

    market_data = cryptsy_py.getMarkets()

    cryptsy_mongo = CryptsyMongo(host="192.168.1.33")

    last_trades = cryptsy_mongo.getLastTrades()

    if len(userMarketIds) > 0:
        market_ids = userMarketIds
    else:
        market_ids = set([int(last_trade['marketid']) for last_trade in last_trades])

    for market_id in market_ids:
        market_name = next((market_name for market_name in market_data if int(market_data[market_name]) == market_id))
        trading_history(market_name, market_id)


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


if __name__ == "__main__":
    main(sys.argv[1:])
