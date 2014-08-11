from datetime import datetime, timedelta
import sys, getopt

import matplotlib.pyplot as plt

from CryptsyMongo import CryptsyMongo, epoch
from CryptsyPy import CryptsyPy


cryptsyClient = None

public = ''
private = ''


def plot_diagram(market_name, market_id):
    interval = timedelta(days=1, hours=4)
    cryptsy_mongo = CryptsyMongo(host="192.168.1.29")
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
    plt.plot(times, prices)
    plt.plot(buy_trade_times, buy_trade_price, 'ro')
    plt.plot(sell_trade_times, sell_trade_price, 'go')
    plt.savefig("{}.png".format("{}-{}".format(market_name.replace('/', '-'), market_id)), format='png')
    plt.close()


def main(argv):

    getEnv(argv)

    cryptsy_py = CryptsyPy(public=public, private=private)

    market_data = cryptsy_py.getMarkets()

    cryptsy_mongo = CryptsyMongo(host="192.168.1.29")

    last_trades = cryptsy_mongo.getLastTrades()

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

if __name__ == "__main__":
    main(sys.argv[1:])