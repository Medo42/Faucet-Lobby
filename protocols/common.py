"""Common helper classes for protocol implementations."""

from __future__ import annotations

from twisted.internet.protocol import Protocol, ClientFactory
from expirationset import expirationset
import config
from server import GameServer, GameServerList

RECENT_ENDPOINTS = expirationset(config.REGISTRATION_THROTTLE_SECS)

# Banned IP list is defined in config


class SimpleTCPReachabilityCheck(Protocol):
    """Attempt to connect to a server to verify it is reachable."""

    def __init__(
        self, server: GameServer, host: str, port: int, serverList: GameServerList
    ) -> None:
        self.__server = server
        self.__host = host
        self.__port = port
        self.__serverList = serverList

    def connectionMade(self):
        print("Connection check successful for %s" % (self.__server))
        self.__serverList.put(self.__server)
        self.transport.loseConnection()


class SimpleTCPReachabilityCheckFactory(ClientFactory):
    """Factory for ``SimpleTCPReachabilityCheck``."""

    def __init__(
        self, server: GameServer, host: str, port: int, serverList: GameServerList
    ) -> None:
        self.__server = server
        self.__host = host
        self.__port = port
        self.__serverList = serverList

    def buildProtocol(self, addr):
        return SimpleTCPReachabilityCheck(
            self.__server, self.__host, self.__port, self.__serverList
        )

    def clientConnectionFailed(self, connector, reason) -> None:
        print("Connection check failed for %s" % (self.__server))
