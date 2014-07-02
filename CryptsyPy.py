import urllib2
import hmac
import ast
import hashlib
import time

import requests

import simplejson


def loadCryptsyMarketData():
    cryptsyApi = "http://pubapi.cryptsy.com/api.php?method=marketdatav2"
    cryptsyMarketDataResponse = urllib2.urlopen(cryptsyApi)
    cryptsyMarketData = simplejson.loads(cryptsyMarketDataResponse.read())
    success = cryptsyMarketData['success']
    if success != 1:
        print "Failed to retrieve Markets"
        exit(-1)
    return cryptsyMarketData


class CryptsyPy:
    def __init__(self, public, private):
        self.public = public
        self.private = private

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
        return responseBody['return'], apiCallSucceded

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

        if apiCallSucceded:
            buyMarkets = []
            for order in orders:
                buyMarkets.append((order['marketid'], order['orderid'], order['created'], order['ordertype']))
        else:
            []

        return buyMarkets