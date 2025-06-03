import uuid
import struct
import re
import socket
from twisted.internet import reactor
from twisted.internet.protocol import Protocol, DatagramProtocol, Factory

import config

from server import GameServer
from protocols.common import (
    SimpleTCPReachabilityCheck,
    SimpleTCPReachabilityCheckFactory,
    RECENT_ENDPOINTS,
)

GG2_BASE_UUID = uuid.UUID("dea41970-4cea-a588-df40-62faef6f1738")
GG2_LOBBY_ID = uuid.UUID("1ccf16b1-436d-856f-504d-cc1af306aaa7")

def gg2_version_to_uuid(data):
    simplever = data[0]
    if simplever == 128:
        return uuid.UUID(bytes=data[1:17])
    else:
        return uuid.UUID(int=GG2_BASE_UUID.int + simplever)

class GG2LobbyQueryV1(Protocol):
    def formatServerData(self, server):
        infostr = b""
        if server.passworded:
            infostr += b"!private!"
        if b"map" in server.infos:
            infostr += b"[" + server.infos[b"map"] + b"] "
        infostr += server.name
        if server.bots == 0:
            infostr += b" [%u/%u]" % (server.players, server.slots)
        else:
            infostr += b" [%u+%u/%u]" % (server.players, server.bots, server.slots)
        infostr = infostr[:255]
        result = bytes([len(infostr)]) + infostr
        result += server.ipv4_endpoint[0]
        result += struct.pack("<H", server.ipv4_endpoint[1])
        return result

    def sendReply(self, protocol_id):
        servers = self.factory.serverList.get_servers_in_lobby(GG2_LOBBY_ID)
        servers = [
            self.formatServerData(server)
            for server in servers
            if server.infos.get(b"protocol_id") == protocol_id.bytes
        ][:255]
        result = bytes([len(servers)]) + b"".join(servers)
        self.transport.write(result)
        self.transport.loseConnection()
        print(
            "Received query for version %s, returned %u Servers." % (protocol_id.hex, len(servers))
        )

    def dataReceived(self, data):
        self.buffered += data
        if len(self.buffered) > 17:
            self.transport.loseConnection()
            return

        if self.buffered[0] != 128 or len(self.buffered) == 17:
            self.sendReply(gg2_version_to_uuid(self.buffered))

    def connectionMade(self):
        self.buffered = b""
        self.timeout = reactor.callLater(
            config.CONNECTION_TIMEOUT_SECS, self.transport.loseConnection
        )

    def connectionLost(self, reason):
        if self.timeout.active():
            self.timeout.cancel()

class GG2LobbyRegV1(DatagramProtocol):
    MAGIC_NUMBERS = bytes([4, 8, 15, 16, 23, 42])
    INFO_PATTERN = re.compile(rb"\A(!private!)?(?:\[([^\]]*)\])?\s*(.*?)\s*(?:\[(\d+)/(\d+)\])?(?: - (.*))?\Z", re.DOTALL)
    CONN_CHECK_FACTORY = Factory()
    CONN_CHECK_FACTORY.protocol = SimpleTCPReachabilityCheck

    def __init__(self, serverList):
        self.serverList = serverList

    def datagramReceived(self, data, addr):
        host, origport = addr
        if (host, origport) in RECENT_ENDPOINTS:
            return
        RECENT_ENDPOINTS.add((host, origport))

        if not data.startswith(GG2LobbyRegV1.MAGIC_NUMBERS):
            return
        data = data[6:]

        if (len(data) < 1) or (data[0] == 128 and len(data) < 17):
            return
        protocol_id = gg2_version_to_uuid(data)
        if data[0] == 128:
            data = data[17:]
        else:
            data = data[1:]

        if len(data) < 3:
            return
        port = struct.unpack("<H", data[:2])[0]
        infolen = data[2]
        infostr = data[3:]
        if len(infostr) != infolen:
            return

        ip = socket.inet_aton(host)
        if ip in config.BANNED_IPS:
            return
        server_id = uuid.UUID(int=GG2_BASE_UUID.int + (struct.unpack("!L", ip)[0] << 16) + port)
        server = GameServer(server_id, GG2_LOBBY_ID)
        server.infos[b"protocol_id"] = protocol_id.bytes
        server.ipv4_endpoint = (ip, port)
        server.infos[b"game"] = b"Legacy Gang Garrison 2 version or mod"
        server.infos[b"game_short"] = b"old"
        matcher = GG2LobbyRegV1.INFO_PATTERN.match(infostr)
        if matcher:
            if matcher.group(1) is not None:
                server.passworded = True
            if matcher.group(2) is not None:
                server.infos[b"map"] = matcher.group(2)
            server.name = matcher.group(3)
            if matcher.group(4) is not None:
                server.players = int(matcher.group(4))
            if matcher.group(5) is not None:
                server.slots = int(matcher.group(5))
            mod = matcher.group(6)
            if mod is not None:
                if mod == b"OHU":
                    server.infos[b"game"] = b"Orpheon's Hosting Utilities"
                    server.infos[b"game_short"] = b"ohu"
                    server.infos[b"game_url"] = b"http://www.ganggarrison.com/forums/index.php?topic=28839.0"
                else:
                    server.infos[b"game"] = mod
                    if len(mod) <= 10:
                        del server.infos[b"game_short"]
        else:
            server.name = infostr
        reactor.connectTCP(
            host,
            port,
            SimpleTCPReachabilityCheckFactory(server, host, port, self.serverList),
            timeout=config.CONNECTION_TIMEOUT_SECS,
        )

class GG2LobbyQueryV1Factory(Factory):
    protocol = GG2LobbyQueryV1

    def __init__(self, serverList):
        self.gg2_lobby_id = GG2_LOBBY_ID
        self.serverList = serverList
