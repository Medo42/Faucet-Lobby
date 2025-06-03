from twisted.web.resource import Resource
from xml.sax.saxutils import escape, quoteattr
import socket
import config

pageTemplate = u"""<!doctype html>
<html>
<head>
    <title>Lobby status page</title>
    <meta http-equiv="content-type"
        content="text/html;charset=utf-8" />
    <link rel="stylesheet" type="text/css" href="style.css" />
</head>
<body>
    <img src="%s" alt="" id=smflogo><div id=head><img src="%s" alt="" id=logo></div>
    %%s
</body>
</html>""" % (config.LOGO_SMFL, config.LOGO_MAIN)

tableTemplate = u"""
    <h2>Active servers in the %s</h2>
    <div id=desc><p>Game information links are provided by the game servers and are not in any way related to this site. You have been warned.</p></div>
    <table class="serverlist">
        <thead>
            <tr>
                <th>PW</th>
                <th>Name</th>
                <th>Map</th>
                <th>Players</th>
                <th>Game</th>
                <th>Address</th>
            </tr>
        </thead><tbody>
            %s
        </tbody>
    </table>
"""

rowTemplate = u"""
                <tr>
                    <td>%s</td>
                    <td>%s</td>
                    <td>%s</td>
                    <td>%s</td>
                    <td>%s</td>
                    <td>%s</td>
                </tr>
"""


def htmlprep(utf8string):
    if isinstance(utf8string, bytes):
        return escape(utf8string.decode('utf-8', 'replace'))
    else:
        return escape(utf8string)

class LobbyStatusResource(Resource):
    isLeaf = True
    
    def __init__(self, serverList):
        self.serverList = serverList
        
    def _format_server(self, server):
        passworded = u"X" if server.passworded else u""
        name = htmlprep(server.name.decode('utf-8', 'replace') if isinstance(server.name, bytes) else server.name)
        map = htmlprep(server.infos[b"map"].decode('utf-8', 'replace')) if b"map" in server.infos else u""
        if(server.bots == 0):
            players = u"%u/%u" % (server.players, server.slots)
        else:
            players = u"%u+%u/%u" % (server.players, server.bots, server.slots)
        if(b"game" in server.infos):
            game = htmlprep(server.infos[b"game"].decode('utf-8', 'replace'))
            game += (u" "+htmlprep(server.infos[b"game_ver"].decode('utf-8', 'replace'))) if (b"game_ver" in server.infos) else u""
            if(b"game_url" in server.infos):
                game = u'<a href=%s>%s</a>' % (quoteattr(server.infos[b"game_url"].decode('utf-8', 'replace')), game)
        else:
            game = u""
        address = (u"%s:%u" % (socket.inet_ntoa(server.ipv4_endpoint[0]), server.ipv4_endpoint[1])) if server.ipv4_endpoint is not None else u""
        return rowTemplate % (passworded, name, map, players, game, address)
        
    def _format_table(self, lobby):
        if lobby in config.KNOWN_LOBBIES:
            lobbyname = escape(config.KNOWN_LOBBIES[lobby])
        else:
            lobbyname = u'unknown lobby "%s"' % lobby.hex
            
        servers = self.serverList.get_servers_in_lobby(lobby)
        serverRows = u"".join([self._format_server(server) for server in servers])
        
        return tableTemplate % (lobbyname,serverRows)
        
    def render_GET(self, request):
        lobbies = self.serverList.get_lobbies()
        lobbyTables = u"".join([self._format_table(lobby) for lobby in lobbies])
        return (pageTemplate % (lobbyTables,)).encode('utf8', 'replace')
