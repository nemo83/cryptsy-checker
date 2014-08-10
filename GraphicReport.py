from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import sys

from CryptsyMongo import CryptsyMongo, epoch


def main(argv):

    market_name = "VTC/BTC"
    interval = timedelta(days=1, hours=4)

    cryptsy_mongo = CryptsyMongo()

    timeStart = datetime.utcnow() - interval

    cryptoCurrencyDataSamples = cryptsy_mongo.markets_collection.find(
        {"name": market_name, "lasttradetime": {"$gt": timeStart.strftime("%Y-%m-%d %H:%M:%S")}})

    tradeData = [(cryptoCurrencySample['lasttradetime'], cryptoCurrencySample['lasttradeprice']) for
                 cryptoCurrencySample in cryptoCurrencyDataSamples]

    uniqueTradeData = set(tradeData)

    times = [(datetime.strptime(tradeDataSample[0], '%Y-%m-%d %H:%M:%S') - epoch).total_seconds()
             for
             tradeDataSample in
             uniqueTradeData]

    prices = [float(tradeDataSample[1]) * 100000000 for tradeDataSample in uniqueTradeData]

    plt.plot(times, prices)
    plt.show()


if __name__ == "__main__":
    main(sys.argv[1:])