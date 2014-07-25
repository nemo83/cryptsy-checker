import urllib2
import hmac
import ast
import hashlib
import time
from datetime import timedelta, datetime
import simplejson

import requests


def loadCryptsyMarketData():
    cryptsyApi = "http://pubapi.cryptsy.com/api.php?method=marketdatav2"
    cryptsyMarketDataResponse = urllib2.urlopen(cryptsyApi)
    cryptsyMarketData = simplejson.loads(cryptsyMarketDataResponse.read())
    success = cryptsyMarketData['success']
    if success != 1:
        print "Failed to retrieve Markets"
    return cryptsyMarketData['return']['markets']


def toEightDigit(value):
    return "%.8f" % round(value, 8)


class CryptsyPy:
    def __init__(self, public, private):
        self.public = public
        self.private = private
        self.markets = None

    def makeAPIcall(self, requestParameters):
        url = 'https://api.cryptsy.com/api'
        message = bytes(requestParameters).encode('utf-8')
        secret = bytes(self.private).encode('utf-8')
        signature = hmac.new(secret, message, digestmod=hashlib.sha512).hexdigest()
        headers = {}
        headers['Key'] = self.public
        headers['Sign'] = signature
        r = requests.post(url, data=requestParameters, headers=headers)
        responseBody = ast.literal_eval(r.content)
        apiCallSucceded = True if int(responseBody['success']) == 1 else False
        if not apiCallSucceded:
            print "CRYPTSY_AUTHENTICATED_API_ERROR [request: {}] [response: {}]".format(requestParameters, responseBody)
        if 'return' in responseBody:
            return responseBody['return'], apiCallSucceded
        else:
            return None, apiCallSucceded

    def getInfo(self):
        requestParameters = "method={}&nonce={}".format("getinfo", int(time.time()))
        response, apiCallSucceded = self.makeAPIcall(requestParameters)
        if apiCallSucceded:
            balances = response['balances_available']
            balanceList = filter(lambda x: x[1] > 0.0, [(balance, float(balances[balance])) for balance in balances])
            return balanceList
        else:
            return []

    def getAllActiveOrders(self):
        postData = "method={}&nonce={}".format("allmyorders", int(time.time()))

        orders, apiCallSucceded = self.makeAPIcall(postData)

        buyMarkets = []
        if apiCallSucceded:
            for order in orders:
                buyMarkets.append(
                    (order['marketid'], order['orderid'], order['created'], order['ordertype'], order['price']))

        return buyMarkets

    def getAllTradesInTheLast(self, numDays):
        enddate = datetime.now()
        startdate = enddate - timedelta(days=numDays)

        postData = "method={}&startdate={}&endate={}&nonce={}".format("allmytrades",
                                                                      startdate.strftime("%Y-%m-%d"),
                                                                      enddate.strftime("%Y-%m-%d"),
                                                                      int(time.time()))
        trades, apiCallSucceded = self.makeAPIcall(postData)

        tradeStats = {}
        if apiCallSucceded:
            for trade in trades:
                marketid = trade['marketid']
                tradetype = trade['tradetype']
                total = trade['total']
                fee = trade['fee']

                if marketid not in tradeStats:
                    tradeStats[marketid] = {}
                    tradeStats[marketid]['NumTrades'] = 0.0
                    tradeStats[marketid]['Buy'] = 0.0
                    tradeStats[marketid]['Sell'] = 0.0
                    tradeStats[marketid]['Fee'] = 0.0

                tradeStats[marketid]['NumTrades'] += 1
                tradeStats[marketid][tradetype] += float(total)
                tradeStats[marketid]['Fee'] += float(fee)

        return tradeStats

    def getBestPerformingMarketsInTheLast(self, numDays):
        tradeStats = self.getAllTradesInTheLast(numDays)
        filteredTradeStats = filter(lambda x: tradeStats[x]['Sell'] > tradeStats[x]['Buy'] > 0, tradeStats)
        sortedTradeStats = sorted(filteredTradeStats, key=lambda x: tradeStats[x]['Sell'] - tradeStats[x]['Buy'],
                                  reverse=True)

        return sortedTradeStats

    def getBestPerformingMarketsInTheLastFeeIncluded(self, numDays):
        tradeStats = self.getAllTradesInTheLast(numDays)
        filteredTradeStats = filter(
            lambda x: tradeStats[x]['Sell'] > tradeStats[x]['Fee'] + tradeStats[x]['Buy'] > 0 and tradeStats[x][
                'Buy'] > 0, tradeStats)
        sortedTradeStats = sorted(filteredTradeStats, key=lambda x: tradeStats[x]['Sell'] - tradeStats[x]['Buy'],
                                  reverse=True)

        return sortedTradeStats

    def getWorstPerformingMarketsInTheLast(self, numDays):
        tradeStats = self.getAllTradesInTheLast(numDays)
        filteredTradeStats = filter(lambda x: 0 < tradeStats[x]['Sell'] < tradeStats[x]['Buy'], tradeStats)
        sortedTradeStats = sorted(filteredTradeStats, key=lambda x: tradeStats[x]['Sell'] - tradeStats[x]['Buy'])

        return sortedTradeStats

    def getWorstPerformingMarketsInTheLastFeeIncluded(self, numDays):
        tradeStats = self.getAllTradesInTheLast(numDays)
        filteredTradeStats = filter(
            lambda x: 0 < tradeStats[x]['Sell'] < tradeStats[x]['Fee'] + tradeStats[x]['Buy'] and tradeStats[x][
                'Buy'] > 0, tradeStats)
        sortedTradeStats = sorted(filteredTradeStats, key=lambda x: tradeStats[x]['Sell'] - tradeStats[x]['Buy'])

        return sortedTradeStats

    def cancelAllOrders(self):
        postData = "method={}&nonce={}".format("cancelallorders", int(time.time()))
        self.makeAPIcall(postData)

    def placeSellOrder(self, marketId, quantity, price):
        postData = "method={}&marketid={}&ordertype=Sell&quantity={}&price={}&nonce={}".format("createorder",
                                                                                               marketId,
                                                                                               toEightDigit(
                                                                                                   quantity),
                                                                                               toEightDigit(
                                                                                                   price),
                                                                                               int(time.time()))
        self.makeAPIcall(postData)

    def placeBuyOrder(self, marketId, quantity, price):
        postData = "method={}&marketid={}&ordertype=Buy&quantity={}&price={}&nonce={}".format("createorder",
                                                                                              marketId,
                                                                                              toEightDigit(
                                                                                                  quantity),
                                                                                              toEightDigit(
                                                                                                  price),
                                                                                              int(time.time()))
        return self.makeAPIcall(postData)

    def cancelOrder(self, orderid):
        postData = "method={}&orderid={}&nonce={}".format("cancelorder", orderid, int(time.time()))
        return self.makeAPIcall(postData)

    def getMarkets(self):
        if self.markets is None:
            postData = "method={}&nonce={}".format("getmarkets", int(time.time()))
            marketData, apiCallSucceded = self.makeAPIcall(postData)
            self.markets = {}
            if apiCallSucceded:
                for market in marketData:
                    market_name = market['label'].replace('\\', '')
                    self.markets[market_name] = market['marketid']
        return self.markets

