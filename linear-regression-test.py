from datetime import date, timedelta, datetime
import time
import urllib2
import getopt
import sys
import hashlib
import hmac
import ast

import requests

import numpy
import simplejson
from pymongo import MongoClient

AMOUNT_TO_INVEST = 0.001


def loadCryptsyMarketData():
    cryptsyApi = "http://pubapi.cryptsy.com/api.php?method=marketdatav2"
    cryptsyMarketDataResponse = urllib2.urlopen(cryptsyApi)
    cryptsyMarketData = simplejson.loads(cryptsyMarketDataResponse.read())
    success = cryptsyMarketData['success']
    if success != 1:
        print "Failed to retrieve Markets"
        exit(-1)
    return cryptsyMarketData


def investBTC(public, private, btcBalance, openBuyMarkets, cryptsyMarketData):
    epoch = datetime.utcfromtimestamp(0)

    marketDetails = cryptsyMarketData['return']['markets']
    marketNames = [market for market in marketDetails]
    client = MongoClient(host="192.168.1.29")
    cryptsyDb = client.cryptsy_database
    marketsCollection = cryptsyDb.markets_collection
    # timeStart = datetime.date.fromordinal(datetime.date.today().toordinal())
    timeStart = date.today() - timedelta(days=1)
    filteredMarketNames = filter(lambda x: 'BTC' in x, marketNames)
    marketTrends = []

    for marketName in filteredMarketNames:

        if marketDetails[marketName]['marketid'] in openBuyMarkets:
            continue

        cryptoCurrencyDataSamples = marketsCollection.find(
            {"name": marketName, "lasttradetime": {"$gt": timeStart.strftime("%Y-%m-%d")}})

        tradeData = [(cryptoCurrencySample['lasttradetime'], cryptoCurrencySample['lasttradeprice']) for
                     cryptoCurrencySample in cryptoCurrencyDataSamples]

        if len(tradeData) == 0:
            continue

        lastTradeTimes = [(datetime.strptime(tradeDataSample[0], '%Y-%m-%d %H:%M:%S') - epoch).total_seconds()
                          for
                          tradeDataSample in
                          tradeData]
        minSeconds = min(lastTradeTimes)
        secondNormalization = max(lastTradeTimes) - minSeconds
        normalizedLastTradeTimes = [(lastTradeTime - minSeconds) / secondNormalization for lastTradeTime in
                                    lastTradeTimes]

        lastTradePrices = [float(tradeDataSample[1]) * 100000000 for tradeDataSample in tradeData]
        minTradingPrice = min(lastTradePrices)
        priceNormalization = max(lastTradePrices) - minTradingPrice
        normalizedLastTradePrices = [
            (lastTradePrice - minTradingPrice) / priceNormalization if priceNormalization != 0 else (
                lastTradePrice - minTradingPrice) for lastTradePrice in
            lastTradePrices]

        currencyTrend = numpy.polyfit(normalizedLastTradeTimes, normalizedLastTradePrices, 1)

        cryptoCurrencyDataSamples = marketsCollection.find(
            {"name": marketName, "lasttradetime": {"$gt": timeStart.strftime("%Y-%m-%d")}})

        prices = [float(cryptoCurrencyDataSample['lasttradeprice']) for cryptoCurrencyDataSample in
                  cryptoCurrencyDataSamples]

        marketTrend = MarketTrend(marketName=marketName, id=marketDetails[marketName]['marketid'], m=currencyTrend[0],
                                  avg=numpy.average(prices),
                                  std=numpy.std(prices))

        marketTrends.append(marketTrend)

    sortedMarketTrends = filter(lambda x: x.m != 0.0 and x.avg >= 0.000001 and x.std > 4 * 0.0025 * x.avg,
                                sorted(marketTrends, key=lambda x: abs(0.0 - x.m)))

    for marketTrend in sortedMarketTrends:
        if btcBalance < AMOUNT_TO_INVEST:
            break

        url = 'https://api.cryptsy.com/api'
        quantity = (AMOUNT_TO_INVEST - AMOUNT_TO_INVEST * 0.0025) / marketTrend.buy

        print "Buy {}, qty: {}, price: {}".format(marketTrend.marketName, quantity, marketTrend.buy)

        postData = "method={}&marketid={}&ordertype=Buy&quantity={}&price={}&nonce={}".format("createorder",
                                                                                              marketTrend.id,
                                                                                              "%.8f" % round(quantity,
                                                                                                             8),
                                                                                              "%.8f" % round(
                                                                                                  marketTrend.buy, 8),

                                                                                              int(time.time()))
        message = bytes(postData).encode('utf-8')
        secret = bytes(private).encode('utf-8')
        signature = hmac.new(secret, message, digestmod=hashlib.sha512).hexdigest()
        headers = {}
        headers['Key'] = public
        headers['Sign'] = signature
        r = requests.post(url, data=postData, headers=headers)
        responseBody = ast.literal_eval(r.content)
        if int(responseBody['success']) != 1:
            print "Error when invoking cryptsy authenticated API"
        else:
            btcBalance -= AMOUNT_TO_INVEST


def main(argv):
    print "Started."

    public, private = getEnv(argv)

    balanceList = getInfo(public, private)

    print "Current Balance:"
    for balance in balanceList:
        print "{}, {}".format(balance[0], balance[1])

    cryptsyMarketData = loadCryptsyMarketData()

    openBuyMarkets = getAllActiveOrders(public, private)

    investBTCFlag = False

    for balance in balanceList:

        if balance[0] == 'BTC':
            investBTCFlag = True
        else:

            marketName = "{}/BTC".format(balance[0])

            client = MongoClient(host="192.168.1.29")
            cryptsyDb = client.cryptsy_database
            marketsCollection = cryptsyDb.markets_collection
            timeStart = date.today() - timedelta(days=1)

            cryptoCurrencyDataSamples = marketsCollection.find(
                {"name": marketName, "lasttradetime": {"$gt": timeStart.strftime("%Y-%m-%d")}})

            prices = [float(cryptoCurrencyDataSample['lasttradeprice']) for cryptoCurrencyDataSample in
                      cryptoCurrencyDataSamples]

            sell = numpy.average(prices) + numpy.std(prices)

            print "Sell {}, qty: {}, price: {}".format(marketName, balance[1], sell)

            url = 'https://api.cryptsy.com/api'
            postData = "method={}&marketid={}&ordertype=Sell&quantity={}&price={}&nonce={}".format("createorder",
                                                                                                   cryptsyMarketData[
                                                                                                       'return'][
                                                                                                       'markets'][
                                                                                                       marketName][
                                                                                                       'marketid'],
                                                                                                   balance[1],
                                                                                                   "%.8f" % round(sell,
                                                                                                                  8),
                                                                                                   int(time.time()))

            message = bytes(postData).encode('utf-8')
            secret = bytes(private).encode('utf-8')
            signature = hmac.new(secret, message, digestmod=hashlib.sha512).hexdigest()
            headers = {}
            headers['Key'] = public
            headers['Sign'] = signature
            r = requests.post(url, data=postData, headers=headers)
            responseBody = ast.literal_eval(r.content)
            if int(responseBody['success']) != 1:
                print "Error when invoking cryptsy authenticated API"

    if investBTCFlag:
        if balance[1] >= AMOUNT_TO_INVEST:
            investBTC(public, private, balance[1], openBuyMarkets, cryptsyMarketData)

    print "Complete"


def getInfo(public, private):
    url = 'https://api.cryptsy.com/api'
    postData = "method={}&nonce={}".format("getinfo", int(time.time()))
    message = bytes(postData).encode('utf-8')
    secret = bytes(private).encode('utf-8')
    signature = hmac.new(secret, message, digestmod=hashlib.sha512).hexdigest()
    headers = {}
    headers['Key'] = public
    headers['Sign'] = signature
    r = requests.post(url, data=postData, headers=headers)
    responseBody = ast.literal_eval(r.content)
    if int(responseBody['success']) != 1:
        print "Error when invoking cryptsy authenticated API"
    balances = responseBody['return']['balances_available']
    balanceList = filter(lambda x: x[1] > 0.0, [(balance, float(balances[balance])) for balance in balances])
    return balanceList


def getAllActiveOrders(public, private):
    url = 'https://api.cryptsy.com/api'
    postData = "method={}&nonce={}".format("allmyorders", int(time.time()))
    message = bytes(postData).encode('utf-8')
    secret = bytes(private).encode('utf-8')
    signature = hmac.new(secret, message, digestmod=hashlib.sha512).hexdigest()
    headers = {}
    headers['Key'] = public
    headers['Sign'] = signature
    r = requests.post(url, data=postData, headers=headers)
    responseBody = ast.literal_eval(r.content)
    if int(responseBody['success']) != 1:
        print "Error when invoking cryptsy authenticated API"
    orders = responseBody['return']

    buyMarkets = []
    for order in orders:
        buyMarkets.append(order['marketid'])

    return buyMarkets


class MarketTrend:
    def __init__(self, marketName, id, m, avg, std):
        self.marketName = marketName
        self.id = id
        self.m = m
        self.avg = avg
        self.std = std
        # self.rate = abs((float(average + std) - float(average - std)) / float(average - std) * 100)
        self.buy = avg - std
        self.sell = avg + std

    def __str__(self):
        return "marketName: {}, id: {}, m: {}, avg: {}, std: {}, buy: {}, sell: {}".format(
            self.marketName,
            self.id,
            self.m,
            self.avg,
            self.std,
            self.buy,
            self.sell
        )


def getEnv(argv):
    public = ''
    private = ''
    try:
        opts, args = getopt.getopt(argv, "h", ["help", "public=", "private="])
    except getopt.GetoptError:
        sys.exit(2)
    for opt, arg in opts:
        if opt in ("-h", "--help"):
            sys.exit()
        elif opt == "--public":
            public = arg
        elif opt == "--private":
            private = arg
    return public, private


if __name__ == "__main__":
    main(sys.argv[1:])