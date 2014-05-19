import urllib2
import datetime

import numpy

import simplejson
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

    filteredMarketNames = filter(lambda x: float(marketDetails[x]['lasttradeprice']) < 0.001, marketNames)

    client = MongoClient()

    cryptsyDb = client.cryptsy_database

    marketsCollection = cryptsyDb.markets_collection

    myMarkets = []

    # timeStart = date.fromordinal(date.today().toordinal() - 1)
    # timeStart = date.fromordinal(date.today().toordinal())
    now = datetime.datetime.now()
    # timeStart = now.replace(day=now.day - 1)
    timeStart = now.replace(hour=now.hour - 1)

    print "time: {}".format(timeStart)

    for marketName in filteredMarketNames:

        sxcBtcPrices = marketsCollection.find(
            {"name": marketName, "lasttradetime": {"$gt": timeStart.strftime("%Y-%m-%d")}})

        if sxcBtcPrices.count() == 0:
            # print "Continuing, marketName: {}".format(marketName)
            continue

        prices = [float(sxcBtcPrice['lasttradeprice']) for sxcBtcPrice in sxcBtcPrices]

        myMarkets.append(MyMarket(marketName=marketName,
                                  min=min(prices),
                                  max=max(prices),
                                  average=numpy.average(prices),
                                  std=numpy.std(prices)))

    # sortedMarkets = sorted(myMarkets, key=lambda x: x.rate, reverse=True)
    # sortedMarkets = sorted(myMarkets, key=lambda x: x.std, reverse=True)
    sortedMarkets = sorted(myMarkets, key=lambda x: x.rate, reverse=True)

    # sortedFilteredMarkets = filter(lambda x: x.average > 0.0001, sortedMarkets)

    for index in range(min(20, len(sortedMarkets))):
        print sortedMarkets[index]


class MyMarket:
    def __init__(self, marketName, min, max, average, std):
        self.marketName = marketName
        self.min = min
        self.max = max
        self.average = average
        self.std = std
        self.rate = abs((float(average + std) - float(average - std)) / float(average - std) * 100)

    def __str__(self):
        return "Name: {}, min: {}, max: {}, avg: {}, std: {}, standardRate: {}, suggestedMinPrice {}, suggestedMaxPrice {}, possibleEarningPerUnit {}".format(
            self.marketName,
            self.min,
            self.max,
            self.std,
            self.average,
            self.rate,
            self.average - self.std,
            self.average + self.std,
            self.std * 2
        )


if __name__ == "__main__":
    main()



