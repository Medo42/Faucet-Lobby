import time, collections, uuid, struct, re, socket, weblist, twisted.web.server, twisted.web.static
from twisted.internet.protocol import Factory, ClientFactory, Protocol, DatagramProtocol
from twisted.internet import reactor
from expirationset import expirationset

class GameServer:
    def __init__(self, server_id, lobby_id):
        self.server_id = server_id
        self.lobby_id = lobby_id
        self.protocol = 0           # 0 = TCP, 1 = UDP
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
        if(self.ipv4_endpoint is not None):
            anonip = self.ipv4_endpoint[0][:-1]+"\0"
            retstr += ", ipv4_endpoint=" + socket.inet_ntoa(anonip)+":"+str(self.ipv4_endpoint[1])
        if(self.ipv6_endpoint is not None):
            anonip = (self.ipv6_endpoint[0][:-10]+"\0"*10, self.ipv6_endpoint[1])
            retstr += ", ipv6_endpoint=" + str(anonip)
        return retstr+">"

class GameServerList:
    def __init__(self, duration=70):
        self._expirationset = expirationset(duration, self._remove_callback)
        self._server_id_dict = {}
        self._endpoint_dict = {}
        self._lobby_dict = {}

    def _remove_callback(self, server_id, expired):
        server = self._server_id_dict.pop(server_id)
        if(server.ipv4_endpoint is not None):
            del self._endpoint_dict[server.ipv4_endpoint]
        if(server.ipv6_endpoint is not None):
            del self._endpoint_dict[server.ipv6_endpoint]
        lobbyset = self._lobby_dict[server.lobby_id]
        lobbyset.remove(server)
        if(not lobbyset):
            del self._lobby_dict[server.lobby_id]

    def put(self, server):
        """ Register a server in the lobby list.

            This server will replace any existing entries for this server ID.
            If an entry for this server ID is already present, its endpoint
            information will be used to complement the known endpoint(s) of the
            new entry, but the old entry itself will be discarded.
            The new server will be rejected if a server with a different ID is
            already known for the same endpoint.

            Warning: Do not modify the server's uuid, lobby or endpoint information
            after registering the server. Make a new server instead and register that."""

        self._expirationset.cleanup_stale()
        
        # Abort if there is a server with the same endpoint and different ID
        if(server.ipv4_endpoint in self._endpoint_dict and self._endpoint_dict[server.ipv4_endpoint] != server.server_id
                or server.ipv6_endpoint in self._endpoint_dict and self._endpoint_dict[server.ipv6_endpoint] != server.server_id):
            print "Server " + str(server) + " rejected - wrong ID for existing endpoint."
            return
            
        # If we already know an alternative endpoint for the server, copy it over.
        try:
            oldserver = self._server_id_dict[server.server_id]
            if(server.ipv4_endpoint is None):
                server.ipv4_endpoint = oldserver.ipv4_endpoint
            if(server.ipv6_endpoint is None):
                server.ipv6_endpoint = oldserver.ipv6_endpoint
        except KeyError:
            pass

        # Remove old entry for the server, if present.
        self._expirationset.discard(server.server_id)

        # Add the new entry
        self._server_id_dict[server.server_id] = server
        if(server.ipv4_endpoint):
            self._endpoint_dict[server.ipv4_endpoint] = server.server_id
        if(server.ipv6_endpoint):
            self._endpoint_dict[server.ipv6_endpoint] = server.server_id
        self._lobby_dict.setdefault(server.lobby_id, set()).add(server)
        self._expirationset.add(server.server_id)
        
    def remove(self, server_id):
        self._expirationset.discard(server_id)
    
    def get_servers_in_lobby(self, lobby_id):
        self._expirationset.cleanup_stale()
        try:
            return self._lobby_dict[lobby_id].copy()
        except KeyError:
            return set()

    def get_lobbies(self):
        return self._lobby_dict.keys()
        
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
        self.timeout = reactor.callLater(5, self.transport.loseConnection)

    def connectionLost(self, reason):
        if(self.timeout.active()): self.timeout.cancel()

class NewStyleList(Protocol):
    LIST_PROTOCOL_ID = uuid.UUID("297d0df4-430c-bf61-640a-640897eaef57")

    def formatKeyValue(self, k, v):
        k = k[:255]
        v = v[:65535]
        return chr(len(k)) + k + struct.pack(">H", len(v)) + v

    def formatServerData(self, server):
        ipv4_endpoint = server.ipv4_endpoint or ("", 0) 
        ipv6_endpoint = server.ipv6_endpoint or ("", 0)
        flags = (1 if server.passworded else 0)
        infos = server.infos.copy()
        infos["name"] = server.name
        result = struct.pack(">BH4sH16sHHHHH", server.protocol, ipv4_endpoint[1], ipv4_endpoint[0], ipv6_endpoint[1], ipv6_endpoint[0], server.slots, server.players, server.bots, flags, len(infos))
        result += "".join([self.formatKeyValue(k, v) for (k, v) in infos.iteritems()])
        return struct.pack(">L", len(result))+result

    def sendReply(self, lobby_id):
        servers = [self.formatServerData(server) for server in self.factory.serverList.get_servers_in_lobby(lobby_id)]
        self.transport.write(struct.pack(">L",len(servers))+"".join(servers))
        print "Received newstyle query for Lobby %s, returned %u Servers." % (lobby_id.hex, len(servers))
    
    def dataReceived(self, data):
        self.buffered += data
        if(len(self.buffered) == 32):
            proto_id = uuid.UUID(bytes=self.buffered[:16])
            if(proto_id == NewStyleList.LIST_PROTOCOL_ID):
                self.sendReply(uuid.UUID(bytes=self.buffered[16:32]))
            else:
                print "Received wrong protocol UUID %s" % (proto_id.hex)
                self.transport.loseConnection()
        if(len(self.buffered) >= 32):
            if(len(self.buffered) > 32):
                print "Received too many bytes: %u" % (len(self.buffered))
            self.transport.loseConnection()
            
    def connectionMade(self):
        self.buffered = ""
        self.list_protocol = None
        self.timeout = reactor.callLater(5, self.transport.loseConnection)

    def connectionLost(self, reason):
        if(self.timeout.active()): self.timeout.cancel()

class SimpleTCPReachabilityCheck(Protocol):
    def __init__(self, server, host, port, serverList):
        self.__server = server
        self.__host = host
        self.__port = port
        self.__serverList = serverList
        
    def connectionMade(self):
        print "Connection check successful for %s" % (self.__server)
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
        print "Connection check failed for %s" % (self.__server)

# TODO: Better flood control using a leaky bucket counter
RECENT_ENDPOINTS = expirationset(10)

# Example IP
BANNED_IP_STRINGS = {"1.2.3.4"}
BANNED_IPS = {socket.inet_aton(x) for x in BANNED_IP_STRINGS}
        
class GG2LobbyRegV1(DatagramProtocol):
    MAGIC_NUMBERS = chr(4)+chr(8)+chr(15)+chr(16)+chr(23)+chr(42)
    INFO_PATTERN = re.compile(r"\A(!private!)?(?:\[([^\]]*)\])?\s*(.*?)\s*(?:\[(\d+)/(\d+)\])?(?: - (.*))?\Z", re.DOTALL)
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
        if(ip in BANNED_IPS): return
        server_id = uuid.UUID(int=GG2_BASE_UUID.int+(struct.unpack("!L",ip)[0]<<16)+port)
        server = GameServer(server_id, GG2_LOBBY_ID)
        server.infos["protocol_id"] = protocol_id.bytes
        server.ipv4_endpoint = (ip, port)
        server.infos["game"] = "Legacy Gang Garrison 2 version or mod";
        server.infos["game_short"] = "old";
        matcher = GG2LobbyRegV1.INFO_PATTERN.match(infostr)
        if(matcher):
            if(matcher.group(1) is not None): server.passworded = True
            if(matcher.group(2) is not None): server.infos["map"] = matcher.group(2)
            server.name = matcher.group(3)
            if(matcher.group(4) is not None): server.players = int(matcher.group(4))
            if(matcher.group(5) is not None): server.slots = int(matcher.group(5))
            if(matcher.group(6) is not None):
                mod = matcher.group(6)
                if(mod=="OHU"):
                    server.infos["game"] = "Orpheon's Hosting Utilities"
                    server.infos["game_short"] = "ohu"
                    server.infos["game_url"] = "http://www.ganggarrison.com/forums/index.php?topic=28839.0"
                else:
                    server.infos["game"] = mod
                    if(len(mod)<=10): del server.infos["game_short"]
        else:
            server.name = infostr
        conn = reactor.connectTCP(host, port, SimpleTCPReachabilityCheckFactory(server, host, port, self.serverList), timeout=5)

class GG2LobbyQueryV1Factory(Factory):
    protocol = GG2LobbyQueryV1

    def __init__(self, serverList):
        self.gg2_lobby_id = uuid.UUID("1ccf16b1-436d-856f-504d-cc1af306aaa7")
        self.serverList = serverList

class NewStyleListFactory(Factory):
    protocol = NewStyleList

    def __init__(self, serverList):
        self.serverList = serverList

class NewStyleReg(DatagramProtocol):
    REG_PROTOCOLS = {}
    
    def __init__(self, serverList):
        self.serverList = serverList
    
    def datagramReceived(self, data, (host, origport)):
        if(len(data) < 16): return
        try:
            reg_protocol = NewStyleReg.REG_PROTOCOLS[uuid.UUID(bytes=data[0:16])]
        except KeyError:
            return
        
        reg_protocol.handle(data, (host, origport), self.serverList)
    
class GG2RegHandler(object):
    def handle(self, data, (host, origport), serverList):
        if((host, origport) in RECENT_ENDPOINTS): return
        RECENT_ENDPOINTS.add((host, origport))
        
        if(len(data) < 61): return
        
        server_id = uuid.UUID(bytes=data[16:32])
        lobby_id = uuid.UUID(bytes=data[32:48])
        server = GameServer(server_id, lobby_id)
        server.protocol = ord(data[48])
        if(server.protocol not in (0,1)): return
        port = struct.unpack(">H", data[49:51])[0]
        if(port == 0): return
        ip = socket.inet_aton(host)
        if(ip in BANNED_IPS): return
        server.ipv4_endpoint = (ip, port)
        server.slots, server.players, server.bots = struct.unpack(">HHH", data[51:57])
        server.passworded = ((ord(data[58]) & 1) != 0)
        kventries = struct.unpack(">H", data[59:61])[0]
        kvtable = data[61:]
        for i in xrange(kventries):
            if(len(kvtable) < 1): return
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
        
        if(server.protocol == 0):
            conn = reactor.connectTCP(host, port, SimpleTCPReachabilityCheckFactory(server, host, port, serverList), timeout=5)
        else:
            serverList.put(server)

# TODO: Prevent datagram reordering from re-registering a server (e.g. block the server ID for a few seconds)
class GG2UnregHandler(object):
    def handle(self, data, (host, origport), serverList):
        if(len(data) != 32): return
        serverList.remove(uuid.UUID(bytes=data[16:32]))
        
NewStyleReg.REG_PROTOCOLS[uuid.UUID("b5dae2e8-424f-9ed0-0fcb-8c21c7ca1352")] = GG2RegHandler()
NewStyleReg.REG_PROTOCOLS[uuid.UUID("488984ac-45dc-86e1-9901-98dd1c01c064")] = GG2UnregHandler()

serverList = GameServerList()
reactor.listenUDP(29942, GG2LobbyRegV1(serverList))
reactor.listenUDP(29944, NewStyleReg(serverList))
reactor.listenTCP(29942, GG2LobbyQueryV1Factory(serverList))
reactor.listenTCP(29944, NewStyleListFactory(serverList))

webres = twisted.web.static.File("httpdocs")
webres.putChild("status", weblist.LobbyStatusResource(serverList))

reactor.listenTCP(29950, twisted.web.server.Site(webres))
reactor.run()
