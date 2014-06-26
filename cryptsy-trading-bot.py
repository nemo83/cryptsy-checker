import time
import hashlib
import hmac
import requests
import base64


def main():
    url = 'https://api.cryptsy.com/api'

    publicApiKey = ''
    secretApiKey = ''

    postData = "method={}&nonce={}".format("getmarkets", int(time.time()))
    print postData

    message = bytes(postData).encode('utf-8')
    secret = bytes(secretApiKey).encode('utf-8')

    sha__digest = hmac.new(secret, message, digestmod=hashlib.sha512).hexdigest()
    signature = base64.b64encode(sha__digest)

    headers = {}
    headers['Key'] = publicApiKey
    headers['Sign'] = sha__digest

    print headers

    r = requests.post(url, data=postData, headers=headers)

    print "Foo:\n {}".format(r.text)


if __name__ == "__main__":
    main()



