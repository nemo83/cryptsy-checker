from datetime import datetime, timedelta
import sys
import getopt

import matplotlib.pyplot as plt

from CryptsyMongo import CryptsyMongo, epoch
from CryptsyPy import CryptsyPy, toCryptsyServerTime


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


def plot_diagram(market_name, market_id):
    interval = timedelta(days=1, hours=4)
    cryptsy_mongo = CryptsyMongo(host="192.168.1.33")
    timeStart = datetime.utcnow() - interval
    cryptoCurrencyDataSamples = cryptsy_mongo.markets_collection.find(
        {"name": market_name, "lasttradetime": {"$gt": timeStart.strftime("%Y-%m-%d %H:%M:%S")}})
    tradeData = [(cryptoCurrencySample['lasttradetime'], cryptoCurrencySample['lasttradeprice']) for
                 cryptoCurrencySample in cryptoCurrencyDataSamples]
    uniqueTradeData = list(set(tradeData))
    uniqueTradeData = sorted(uniqueTradeData, key=(lambda x: x[0]))
    times = [(datetime.strptime(tradeDataSample[0], '%Y-%m-%d %H:%M:%S') - epoch).total_seconds()
             for tradeDataSample in uniqueTradeData]
    prices = [float(tradeDataSample[1]) for tradeDataSample in uniqueTradeData]
    trades = cryptsy_mongo.trades_collection.find(
        {"marketid": str(market_id), "datetime": {"$gt": timeStart.strftime("%Y-%m-%d %H:%M:%S")}})
    trade_samples = []
    for trade in trades:
        trade_samples.append(((datetime.strptime(trade['datetime'], '%Y-%m-%d %H:%M:%S') - epoch).total_seconds(),
                              float(trade['tradeprice']), trade['tradetype']))
    buy_trade_times = [trade_sample[0] for trade_sample in trade_samples if trade_sample[2] == 'Buy']
    buy_trade_price = [trade_sample[1] for trade_sample in trade_samples if trade_sample[2] == 'Buy']
    sell_trade_times = [trade_sample[0] for trade_sample in trade_samples if trade_sample[2] == 'Sell']
    sell_trade_price = [trade_sample[1] for trade_sample in trade_samples if trade_sample[2] == 'Sell']

    colours = {
        0 : "k",
        4 : "m",
        8 : "g",
        12 : "c",
        16 : "b",
        20 : "y",
        24 : "k",
    }

    increment = 4
    for m_hour in range(0, 24, increment):
        times_x = []
        prices_y = []
        market_trend = cryptsy_mongo.calculateMarketTrend(market_name, market_id,
                                                          interval=timedelta(days=1, hours=4 + (24 - m_hour)),
                                                          end_time=datetime.utcnow() - timedelta(hours=4 + (24 - m_hour)))
        if market_trend.m == 0.0 or market_trend.scalingFactorX == 0.0:
            continue

        for hour in range(0, m_hour + increment, 1):
            time_x = datetime.utcnow() - timedelta(hours=24 - hour)
            price_y = getNormalizedEstimatedPrice(market_trend, time_x)
            times_x.append((toCryptsyServerTime(time_x) - epoch).total_seconds())
            prices_y.append(price_y)
            plt.plot(times_x, prices_y, "{}o".format(colours[m_hour]))

    plt.plot(times, prices)
    plt.plot(buy_trade_times, buy_trade_price, 'ro')
    plt.plot(sell_trade_times, sell_trade_price, 'go')
    plt.savefig("{}.png".format("{}-{}".format(market_name.replace('/', '-'), market_id)), format='png')
    plt.close()


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
        plot_diagram(market_name, market_id)


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
