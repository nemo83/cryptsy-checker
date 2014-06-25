#!/usr/bin/python
import urllib2
import datetime

import simplejson
from pymongo.mongo_client import MongoClient


class Market:
    def __init__(self, marketid, name, lasttradeprice, lasttradetime):
        self.marketid = marketid
        self.name = name
        self.lasttradeprice = lasttradeprice
        self.lasttradetime = lasttradetime


def main():
    cryptsyApi = "http://pubapi.cryptsy.com/api.php?method=marketdatav2"

    cryptsyMarketDataResponse = urllib2.urlopen(cryptsyApi)
    cryptsyMarketData = simplejson.loads(cryptsyMarketDataResponse.read())

    success = cryptsyMarketData['success']

    if success == 1:
        markets = cryptsyMarketData['return']['markets']

        allMarkets = []

        for market in markets:
            allMarkets.append(Market(marketid=markets[market]["marketid"],
                                     name=markets[market]["label"],
                                     lasttradeprice=markets[market]["lasttradeprice"],
                                     lasttradetime=markets[market]["lasttradetime"]))

        activeMarkets = filter(lambda x: x.lasttradeprice is not None and float(x.lasttradeprice) != 0.0, allMarkets)

        client = MongoClient()

        cryptsyDb = client.cryptsy_database

        marketsCollection = cryptsyDb.markets_collection

        for market in activeMarkets:
            marketsCollection.insert(market.__dict__)

        print "{} - Completed!".format(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        exit(0)
    else:
        print "{} - Failed to retrieve markets".format(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        exit(-1, "Error")


if __name__ == "__main__":
    main()



