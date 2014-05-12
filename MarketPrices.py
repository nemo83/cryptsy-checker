from pymongo import MongoClient
import numpy

def main():
    client = MongoClient()

    cryptsyDb = client.cryptsy_database

    marketsCollection = cryptsyDb.markets_collection

    sxcBtcPrices = marketsCollection.find({"name": "SXC/BTC"})

    prices = [float(sxcBtcPrice['lasttradeprice']) for sxcBtcPrice in sxcBtcPrices]

    print "Min price: {}".format(min(prices))
    print "Max price: {}".format(max(prices))

    print "Average price: {}".format(numpy.mean(prices))
    print "Standard Deviation price: {}".format(numpy.std(prices))

    print "SXC/BTC entries: {}".format(sxcBtcPrices.count())


if __name__ == "__main__":
    main()
