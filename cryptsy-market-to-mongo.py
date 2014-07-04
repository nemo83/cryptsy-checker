#!/usr/bin/python
import urllib2
import datetime

import simplejson
from pymongo.mongo_client import MongoClient


class Market:
    def __init__(self, marketid, tradeid, name, lasttradeprice, lasttradetime):
        self.marketid = marketid
        self.tradeid = tradeid
        self.name = name
        self.lasttradeprice = lasttradeprice
        self.lasttradetime = lasttradetime

    def __str__(self):
        return "marketid: {}, tradeid: {}, name: {}, lasttradeprice:{}, lasttradetime: {}".format(self.marketid,
                                                                                                  self.tradeid,
                                                                                                  self.name,
                                                                                                  self.lasttradeprice,
                                                                                                  self.lasttradetime)


def main():

    client = MongoClient()
    cryptsyDb = client.cryptsy_database
    marketsCollection = cryptsyDb.markets_collection
    result = marketsCollection.find().sort('tradeid', -1).limit(1)
    maxtradeid = 0
    if result.count() > 0:
        maxtradeid = result[0]['tradeid']

    cryptsyApi = "http://pubapi.cryptsy.com/api.php?method=marketdatav2"

    cryptsyMarketDataResponse = urllib2.urlopen(cryptsyApi)
    cryptsyMarketData = simplejson.loads(cryptsyMarketDataResponse.read())

    success = cryptsyMarketData['success']

    if success == 1:
        markets = cryptsyMarketData['return']['markets']

        allMarkets = []

        for market in markets:
            if 'recenttrades' in markets[market] and markets[market]['recenttrades'] is not None:
                for recenttrade in markets[market]['recenttrades']:
                    allMarkets.append(Market(marketid=markets[market]["marketid"],
                                             tradeid=recenttrade['id'],
                                             name=markets[market]["label"],
                                             lasttradeprice=recenttrade['price'],
                                             lasttradetime=recenttrade['time']))

        activeMarkets = filter(
            lambda x: x.lasttradeprice is not None and float(x.lasttradeprice) != 0.0 and x.tradeid > maxtradeid,
            allMarkets)

        for market in activeMarkets:
            marketsCollection.insert(market.__dict__)

        print "{} - Completed!".format(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        exit(0)
    else:
        print "{} - Failed to retrieve markets".format(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        exit(-1, "Error")


if __name__ == "__main__":
    main()



