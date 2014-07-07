import sys
import getopt

from CryptsyPy import CryptsyPy


cryptsyClient = None

public = ''
private = ''


def main(argv):
    getEnv(argv)

    global cryptsyClient
    cryptsyClient = CryptsyPy(public, private)

    cryptsyClient.cancelAllOrders()


def getEnv(argv):
    global public
    global private
    global userMarketIds
    try:
        opts, args = getopt.getopt(argv, "h", ["help", "public=", "private=", "marketIds="])
    except getopt.GetoptError:
        sys.exit(2)
    for opt, arg in opts:
        if opt in ("-h", "--help"):
            sys.exit()
        elif opt == "--public":
            public = arg
        elif opt == "--private":
            private = arg
        elif opt == "--marketIds":
            userMarketIds = arg.split(",")


if __name__ == "__main__":
    main(sys.argv[1:])