import urllib2
import simplejson
from datetime import date
from datetime import datetime

import numpy

from pymongo import MongoClient


def main():
    cryptsyApi = "http://pubapi.cryptsy.com/api.php?method=marketdatav2"

    cryptsyMarketDataResponse = urllib2.urlopen(cryptsyApi)
    cryptsyMarketData = simplejson.loads(cryptsyMarketDataResponse.read())

    success = cryptsyMarketData['success']

    if success != 1:
        print "Failed to retrieve Markets"
        exit(-1)

    marketDetails = cryptsyMarketData['return']['markets']

    marketNames = [market for market in marketDetails]
    # marketNames = filter(lambda x: float(x.lasttradeprice) != 0.0, marketDetails)

    client = MongoClient()

    cryptsyDb = client.cryptsy_database

    marketsCollection = cryptsyDb.markets_collection

    myMarkets = []

    # yesterday = date.fromordinal(date.today().toordinal() - 1)
    yesterday = date.fromordinal(date.today().toordinal())

    for marketName in marketNames:
        sxcBtcPrices = marketsCollection.find(
            {"name": marketName, "lasttradetime": {"$gt": yesterday.strftime("%Y-%m-%d")}})

        if sxcBtcPrices.count() == 0:
            # print "Continuing, marketName: {}".format(marketName)
            continue

        prices = [float(sxcBtcPrice['lasttradeprice']) for sxcBtcPrice in sxcBtcPrices]

        myMarkets.append(MyMarket(marketName=marketName,
                                  min=min(prices),
                                  max=max(prices),
                                  std=numpy.std(prices)))

    sortedMarkets = sorted(myMarkets, key=lambda x: x.rate, reverse=True)

    for index in range(min(10, len(sortedMarkets))):
        print sortedMarkets[index]


class MyMarket:
    def __init__(self, marketName, min, max, std):
        self.marketName = marketName
        self.min = min
        self.max = max
        self.std = std
        self.rate = abs((float(max) - float(min)) / float(min) * 100)

    def __str__(self):
        return "Name: {}, min: {}, max: {}, std: {}, rate: {}".format(self.marketName,
                                                                      self.min,
                                                                      self.max,
                                                                      self.std,
                                                                      self.rate)


if __name__ == "__main__":
    main()



