import time, collections, uuid, struct, re, socket
from twisted.internet.protocol import Factory, ClientFactory, Protocol, DatagramProtocol
from twisted.internet import reactor
from expirationset import expirationset

class GameServer:
    def __init__(self, server_id, lobby_id):
        self.server_id = server_id
        self.lobby_id = lobby_id
        self.ipv4_endpoint = None   # Tuple: (ipv4, port), as binary string and int
        self.ipv6_endpoint = None   # Tuple: (ipv6, port), as binary string and int

        self.name = ""
        self.slots = 0
        self.players = 0
        self.bots = 0
        self.passworded = False
        
        self.infos = {}

    def __repr__(self):
        retstr = "<GameServer, name="+self.name+", lobby_id="+str(self.lobby_id)
        if(self.ipv4_endpoint is not None) : retstr += ", ipv4_endpoint=" + socket.inet_ntoa(self.ipv4_endpoint[0])+":"+str(self.ipv4_endpoint[1])
        if(self.ipv6_endpoint is not None) : retstr += ", ipv6_endpoint=" + str(self.ipv6_endpoint)
        return retstr+">"

class GameServerList:
    def __init__(self, duration=70):
        self._expirationset = expirationset(duration, self._remove_callback)
        self._server_id_dict = {}
        self._v4_dict = {}
        self._v6_dict = {}
        self._lobby_dict = {}

    def _remove_callback(self, server_id, expired):
        server = self._server_id_dict.pop(server_id)
        if(server.ipv4_endpoint is not None):
            del self._v4_dict[server.ipv4_endpoint]
        if(server.ipv6_endpoint is not None):
            del self._v6_dict[server.ipv6_endpoint]
        lobbyset = self._lobby_dict[server.lobby_id]
        lobbyset.remove(server)
        if(not lobbyset):
            del self._lobby_dict[server.lobby_id]

    def put(self, server):
        """ Register a server in the lobby list.

            This server will replace any existing entries for this server ID,
            as well as any entries with a coinciding endpoint.
            If an entry for this server ID is already present, its endpoint
            information will be used to complement the known endpoint(s) of the
            new entry, but the old entry itself will be discarded.

            Warning: Do not modify the server's uuid, lobby or endpoint information
            after registering the server."""

        # If we already know an alternative endpoint for the server, copy it over.
        try:
            oldserver = self._server_id_dict[server.server_id]
            if(server.ipv4_endpoint is None):
                server.ipv4_endpoint = oldserver.ipv4_endpoint
            if(server.ipv6_endpoint is None):
                server.ipv6_endpoint = oldserver.ipv6_endpoint
        except KeyError:
            pass

        # Remove any old entry for the server.
        # Also removes servers which share endpoints with the new one,
        # to prevent people from filling up the server list by generating
        # bogus IDs all pointing to the same actual server.
        if(server.server_id in self._server_id_dict):
            self._expirationset.discard(server.server_id)
        if(server.ipv4_endpoint in self._v4_dict):
            self._expirationset.discard(self._v4_dict[server.ipv4_endpoint])
        if(server.ipv6_endpoint in self._v6_dict):
            self._expirationset.discard(self._v6_dict[server.ipv6_endpoint])

        # Add the new entry
        self._server_id_dict[server.server_id] = server
        if(server.ipv4_endpoint):
            self._v4_dict[server.ipv4_endpoint] = server.server_id
        if(server.ipv6_endpoint):
            self._v6_dict[server.ipv6_endpoint] = server.server_id
        try:
            self._lobby_dict[server.lobby_id].add(server)
        except KeyError:
            lobbyset = set((server,))
            self._lobby_dict[server.lobby_id] = lobbyset
        self._expirationset.add(server.server_id)
        
    def get_servers_in_lobby(self, lobby_id):
        self._expirationset.cleanup_stale()
        try:
            return self._lobby_dict[lobby_id].copy()
        except KeyError:
            return set()


GG2_BASE_UUID = uuid.UUID("dea41970-4cea-a588-df40-62faef6f1738")
GG2_LOBBY_ID = uuid.UUID("1ccf16b1-436d-856f-504d-cc1af306aaa7")
def gg2_version_to_uuid(data):
    simplever = ord(data[0])
    if(simplever==128):
        return uuid.UUID(bytes=data[1:17])
    else:
        return uuid.UUID(int=GG2_BASE_UUID.int+simplever)


class GG2LobbyQueryV1(Protocol):
    def formatServerData(self, server):
        infostr = ""
        if(server.passworded): infostr += "!private!"
        if("map" in server.infos): infostr += "["+server.infos["map"]+"] "
        infostr += server.name
        if(server.bots == 0):
            infostr += " [%u/%u]" % (server.players, server.slots)
        else:
            infostr += " [%u+%u/%u]" % (server.players, server.bots, server.slots)
        infostr = infostr[:255]
        result = chr(len(infostr))+infostr
        result += server.ipv4_endpoint[0]
        result += struct.pack("<H",server.ipv4_endpoint[1])
        return result
        
    def sendReply(self, protocol_id):
        servers = self.factory.serverList.get_servers_in_lobby(GG2_LOBBY_ID)
        servers = [self.formatServerData(server) for server in servers if server.infos.get("protocol_id")==protocol_id.bytes][:255]
        self.transport.write(chr(len(servers))+"".join(servers))
        self.transport.loseConnection()
        print "Received query for version %s, returned %u Servers." % (protocol_id.hex, len(servers))
    
    def dataReceived(self, data):
        self.buffered += data
        if(len(self.buffered) > 17):
            self.transport.loseConnection()
            return

        if(ord(self.buffered[0]) != 128 or len(self.buffered)==17):
            self.sendReply(gg2_version_to_uuid(self.buffered))
            
    def connectionMade(self):
        self.buffered = ""
        self.timeout = reactor.callLater(3, self.transport.loseConnection)

    def connectionLost(self, reason):
        if(self.timeout.active()): self.timeout.cancel()

class SimpleTCPReachabilityCheck(Protocol):
    def __init__(self, server, host, port, serverList):
        self.__server = server
        self.__host = host
        self.__port = port
        self.__serverList = serverList
        
    def connectionMade(self):
        print "Connection check successful for %s@%s:%i" % (self.__server.name, self.__host, self.__port)
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
        print "Connection check failed for %s@%s:%i" % (self.__server.name, self.__host, self.__port)

RECENT_ENDPOINTS = expirationset(10)
        
class GG2LobbyRegV1(DatagramProtocol):
    MAGIC_NUMBERS = chr(4)+chr(8)+chr(15)+chr(16)+chr(23)+chr(42)
    INFO_PATTERN = re.compile(r"\A(!private!)?(?:\[([^\]]*)\])?\s*(.*?)\s*(?:\[(\d+)/(\d+)\])?(?: - OHU)?\Z", re.DOTALL)
    CONN_CHECK_FACTORY = Factory()
    CONN_CHECK_FACTORY.protocol = SimpleTCPReachabilityCheck
        
    def __init__(self, serverList):
        self.serverList = serverList
    
    def datagramReceived(self, data, (host, origport)):
        if((host, origport) in RECENT_ENDPOINTS): return
        RECENT_ENDPOINTS.add((host, origport))
        
        if(not data.startswith(GG2LobbyRegV1.MAGIC_NUMBERS)): return
        data = data[6:]
        
        if((len(data) < 1) or (ord(data[0])==128 and len(data) < 17)): return
        protocol_id = gg2_version_to_uuid(data)
        if(ord(data[0])==128): data = data[17:]
        else: data = data[1:]

        if((len(data) < 3)): return
        port = struct.unpack("<H", data[:2])[0]
        infolen = ord(data[2])
        infostr = data[3:]
        if(len(infostr) != infolen): return

        ip = socket.inet_aton(host)
        server_id = uuid.UUID(int=GG2_BASE_UUID.int+(struct.unpack("!L",ip)[0]<<16)+port)
        server = GameServer(server_id, GG2_LOBBY_ID)
        server.infos["protocol_id"] = protocol_id.bytes
        server.ipv4_endpoint = (ip, port)
        matcher = GG2LobbyRegV1.INFO_PATTERN.match(infostr)
        if(matcher):
            if(matcher.group(1) is not None): server.passworded = True
            if(matcher.group(2) is not None): server.infos["map"] = matcher.group(2)
            server.name = matcher.group(3)
            if(matcher.group(4) is not None): server.players = int(matcher.group(4))
            if(matcher.group(5) is not None): server.slots = int(matcher.group(5))
        else:
            server.name = infostr
        conn = reactor.connectTCP(host, port, SimpleTCPReachabilityCheckFactory(server, host, port, self.serverList), timeout=5)

class GG2LobbyQueryV1Factory(Factory):
    protocol = GG2LobbyQueryV1

    def __init__(self, serverList):
        self.gg2_lobby_id = uuid.UUID("1ccf16b1-436d-856f-504d-cc1af306aaa7")
        self.serverList = serverList

class NewStyleReg(DatagramProtocol):
    REG_PROTOCOLS = {}
    
    def __init__(self, serverList):
        self.serverList = serverList
    
    def datagramReceived(self, data, (host, origport)):
        if((host, origport) in RECENT_ENDPOINTS): return
        RECENT_ENDPOINTS.add((host, origport))
        
        if(len(data) < 16): return
        try:
            reg_protocol = NewStyleReg.REG_PROTOCOLS[uuid.UUID(bytes=data[0:16])]
        except KeyError:
            return
        
        reg_protocol.handle(data, (host, origport), self.serverList)
    
class GG2RegHandler(object):
    def handle(self, data, (host, origport), serverList):
        if(len(data) < 59): return
        
        server_id = uuid.UUID(bytes=data[16:32])
        lobby_id = uuid.UUID(bytes=data[32:48])
        server = GameServer(server_id, lobby_id)
        if(ord(data[48]) != 0): return
        port = struct.unpack(">H", data[49:51])[0]
        if(port == 0): return
        ip = socket.inet_aton(host)
        server.ipv4_endpoint = (ip, port)
        
        server.slots = struct.unpack(">H", data[51:53])[0]
        server.players = struct.unpack(">H", data[53:55])[0]
        server.bots = struct.unpack(">H", data[55:57])[0]
        
        server.passworded = ((ord(data[58]) & 1) != 0)
        kvtable = data[59:]
        while(kvtable):
            keylen = ord(kvtable[0])
            valueoffset = keylen+3
            if(len(kvtable) < valueoffset): return
            key = kvtable[1:keylen+1]
            
            valuelen = struct.unpack(">H", kvtable[keylen+1:valueoffset])[0]
            if(len(kvtable) < valueoffset+valuelen): return
            value = kvtable[valueoffset:valueoffset+valuelen]
            server.infos[key] = value
            kvtable = kvtable[valueoffset+valuelen:]
            
        try:
            server.name = server.infos.pop("name")
        except KeyError:
            return
        
        conn = reactor.connectTCP(host, port, SimpleTCPReachabilityCheckFactory(server, host, port, serverList), timeout=5)
        
NewStyleReg.REG_PROTOCOLS[uuid.UUID("b5dae2e8-424f-9ed0-0fcb-8c21c7ca1352")] = GG2RegHandler()
        
serverList = GameServerList()
reactor.listenUDP(29942, GG2LobbyRegV1(serverList))
reactor.listenUDP(29944, NewStyleReg(serverList))
reactor.listenTCP(29942, GG2LobbyQueryV1Factory(serverList))
reactor.run()
