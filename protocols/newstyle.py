import uuid
import struct
import socket
from twisted.internet import reactor
from twisted.internet.protocol import Protocol, Factory, DatagramProtocol

import config

from server import GameServer
from protocols.common import (
    SimpleTCPReachabilityCheckFactory,
    RECENT_ENDPOINTS,
)

class NewStyleList(Protocol):
    LIST_PROTOCOL_ID = uuid.UUID("297d0df4-430c-bf61-640a-640897eaef57")

    def formatKeyValue(self, k, v):
        k = k[:255]
        v = v[:65535]
        return bytes([len(k)]) + k + struct.pack(">H", len(v)) + v

    def formatServerData(self, server):
        ipv4_endpoint = server.ipv4_endpoint or (b"\x00" * 4, 0)
        ipv6_endpoint = server.ipv6_endpoint or (b"\x00" * 16, 0)
        flags = 1 if server.passworded else 0
        infos = server.infos.copy()
        infos[b"name"] = server.name
        result = struct.pack(
            ">BH4sH16sHHHHH",
            server.protocol,
            ipv4_endpoint[1],
            ipv4_endpoint[0],
            ipv6_endpoint[1],
            ipv6_endpoint[0],
            server.slots,
            server.players,
            server.bots,
            flags,
            len(infos),
        )
        result += b"".join([self.formatKeyValue(k, v) for (k, v) in infos.items()])
        return struct.pack(">L", len(result)) + result

    def sendReply(self, lobby_id):
        servers = [
            self.formatServerData(server)
            for server in self.factory.serverList.get_servers_in_lobby(lobby_id)
        ]
        self.transport.write(struct.pack(">L", len(servers)) + b"".join(servers))
        print(
            "Received newstyle query for Lobby %s, returned %u Servers." % (lobby_id.hex, len(servers))
        )

    def dataReceived(self, data):
        self.buffered += data
        if len(self.buffered) == 32:
            proto_id = uuid.UUID(bytes=self.buffered[:16])
            if proto_id == NewStyleList.LIST_PROTOCOL_ID:
                self.sendReply(uuid.UUID(bytes=self.buffered[16:32]))
            else:
                print("Received wrong protocol UUID %s" % (proto_id.hex))
                self.transport.loseConnection()
        if len(self.buffered) >= 32:
            if len(self.buffered) > 32:
                print("Received too many bytes: %u" % (len(self.buffered)))
            self.transport.loseConnection()

    def connectionMade(self):
        self.buffered = b""
        self.list_protocol = None
        self.timeout = reactor.callLater(
            config.CONNECTION_TIMEOUT_SECS, self.transport.loseConnection
        )

    def connectionLost(self, reason):
        if self.timeout.active():
            self.timeout.cancel()

class NewStyleListFactory(Factory):
    protocol = NewStyleList

    def __init__(self, serverList):
        self.serverList = serverList

class NewStyleReg(DatagramProtocol):
    REG_PROTOCOLS = {}

    def __init__(self, serverList):
        self.serverList = serverList

    def datagramReceived(self, data, addr):
        host, origport = addr
        if len(data) < 16:
            return
        try:
            reg_protocol = NewStyleReg.REG_PROTOCOLS[uuid.UUID(bytes=data[0:16])]
        except KeyError:
            return

        reg_protocol.handle(data, (host, origport), self.serverList)

class GG2RegHandler:
    def handle(self, data, addr, serverList):
        host, origport = addr
        if (host, origport) in RECENT_ENDPOINTS:
            return
        RECENT_ENDPOINTS.add((host, origport))

        if len(data) < 61:
            return

        server_id = uuid.UUID(bytes=data[16:32])
        lobby_id = uuid.UUID(bytes=data[32:48])
        server = GameServer(server_id, lobby_id)
        server.protocol = data[48]
        if server.protocol not in (0, 1):
            return
        port = struct.unpack(">H", data[49:51])[0]
        if port == 0:
            return
        ip = socket.inet_aton(host)
        if ip in config.BANNED_IPS:
            return
        server.ipv4_endpoint = (ip, port)
        server.slots, server.players, server.bots = struct.unpack(">HHH", data[51:57])
        server.passworded = (data[58] & 1) != 0
        kventries = struct.unpack(">H", data[59:61])[0]
        kvtable = data[61:]
        for _ in range(kventries):
            if len(kvtable) < 1:
                return
            keylen = kvtable[0]
            valueoffset = keylen + 3
            if len(kvtable) < valueoffset:
                return
            key = kvtable[1 : keylen + 1]

            valuelen = struct.unpack(">H", kvtable[keylen + 1 : valueoffset])[0]
            if len(kvtable) < valueoffset + valuelen:
                return
            value = kvtable[valueoffset : valueoffset + valuelen]
            server.infos[key] = value
            kvtable = kvtable[valueoffset + valuelen :]

        try:
            server.name = server.infos.pop(b"name")
        except KeyError:
            return

        if server.protocol == 0:
            reactor.connectTCP(
                host,
                port,
                SimpleTCPReachabilityCheckFactory(server, host, port, serverList),
                timeout=config.CONNECTION_TIMEOUT_SECS,
            )
        else:
            serverList.put(server)

class GG2UnregHandler:
    def handle(self, data, addr, serverList):
        host, origport = addr
        if len(data) != 32:
            return
        serverList.remove(uuid.UUID(bytes=data[16:32]))

# Register handlers for GG2-style servers
NewStyleReg.REG_PROTOCOLS[uuid.UUID("b5dae2e8-424f-9ed0-0fcb-8c21c7ca1352")] = GG2RegHandler()
NewStyleReg.REG_PROTOCOLS[uuid.UUID("488984ac-45dc-86e1-9901-98dd1c01c064")] = GG2UnregHandler()
