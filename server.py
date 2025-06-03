import socket
from expirationset import expirationset

class GameServer:
    def __init__(self, server_id, lobby_id):
        self.server_id = server_id
        self.lobby_id = lobby_id
        self.protocol = 0           # 0 = TCP, 1 = UDP
        self.ipv4_endpoint = None   # Tuple: (ipv4, port)
        self.ipv6_endpoint = None   # Tuple: (ipv6, port)

        self.name = b""
        self.slots = 0
        self.players = 0
        self.bots = 0
        self.passworded = False

        self.infos = {}

    def __repr__(self):
        retstr = "<GameServer, name="+self.name.decode('utf-8', 'replace')+", lobby_id="+str(self.lobby_id)
        if(self.ipv4_endpoint is not None):
            anonip = self.ipv4_endpoint[0][:-1]+b"\0"
            retstr += ", ipv4_endpoint=" + socket.inet_ntoa(anonip)+":"+str(self.ipv4_endpoint[1])
        if(self.ipv6_endpoint is not None):
            anonip = (self.ipv6_endpoint[0][:-10]+b"\0"*10, self.ipv6_endpoint[1])
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
        self._expirationset.cleanup_stale()
        if(server.ipv4_endpoint in self._endpoint_dict and self._endpoint_dict[server.ipv4_endpoint] != server.server_id
                or server.ipv6_endpoint in self._endpoint_dict and self._endpoint_dict[server.ipv6_endpoint] != server.server_id):
            print("Server " + str(server) + " rejected - wrong ID for existing endpoint.")
            return
        try:
            oldserver = self._server_id_dict[server.server_id]
            if(server.ipv4_endpoint is None):
                server.ipv4_endpoint = oldserver.ipv4_endpoint
            if(server.ipv6_endpoint is None):
                server.ipv6_endpoint = oldserver.ipv6_endpoint
        except KeyError:
            pass

        self._expirationset.discard(server.server_id)
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
