from datetime import datetime, timedelta
import sys

import matplotlib.pyplot as plt

from CryptsyMongo import CryptsyMongo, epoch


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
        {"marketid": market_id, "datetime": {"$gt": timeStart.strftime("%Y-%m-%d %H:%M:%S")}})
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
    plt.savefig("{}.png".format(market_id), format='png')
    plt.close()


def main(argv):

    # markets = [("VTC/BTC", "151"), ("RZR/BTC", "237"), ("SXC/BTC", "153"), ("RZR/BTC", "66"), ("ANC/BTC", "237"), ("VIA/BTC", "261"), ("FTC/BTC", "5")]
    # markets = [("BTCD/BTC", "256")]
    markets = [("CLOAK/BTC", "227")]

    # market_name = "VTC/BTC"
    # market_id = "151"

    for market in markets:
        plot_diagram(market[0], market[1])


if __name__ == "__main__":
    main(sys.argv[1:])