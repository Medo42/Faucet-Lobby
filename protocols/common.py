import socket
from twisted.internet.protocol import Protocol, ClientFactory
from expirationset import expirationset

RECENT_ENDPOINTS = expirationset(10)

# Example IP
BANNED_IP_STRINGS = {"1.2.3.4"}
BANNED_IPS = {socket.inet_aton(x) for x in BANNED_IP_STRINGS}

class SimpleTCPReachabilityCheck(Protocol):
    def __init__(self, server, host, port, serverList):
        self.__server = server
        self.__host = host
        self.__port = port
        self.__serverList = serverList

    def connectionMade(self):
        print("Connection check successful for %s" % (self.__server))
        self.__serverList.put(self.__server)
        self.transport.loseConnection()

class SimpleTCPReachabilityCheckFactory(ClientFactory):
    def __init__(self, server, host, port, serverList):
        self.__server = server
        self.__host = host
        self.__port = port
        self.__serverList = serverList

    def buildProtocol(self, addr):
        return SimpleTCPReachabilityCheck(self.__server, self.__host, self.__port, self.__serverList)

    def clientConnectionFailed(self, connector, reason):
        print("Connection check failed for %s" % (self.__server))
