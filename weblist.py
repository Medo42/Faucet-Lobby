from twisted.web.resource import Resource
from xml.sax.saxutils import escape, quoteattr
import uuid, socket

pageTemplate = u"""<!doctype html>
<html>
<head>
    <title>Lobby status page</title>
    <meta http-equiv="content-type" 
        content="text/html;charset=utf-8" />
    <link rel="stylesheet" type="text/css" href="style.css" />  
</head>
<body>
    <img src="http://static.ganggarrison.com/Themes/GG2/images/smflogo.gif" alt="" id=smflogo><div id=head><img src="http://static.ganggarrison.com/GG2ForumLogo.png" alt="" id=logo></div>
    %s
</body>
</html>"""

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

knownLobbies = {
    uuid.UUID("1ccf16b1-436d-856f-504d-cc1af306aaa7") : u"Gang Garrison Lobby",
    uuid.UUID("0e29560e-443a-93a3-e15e-7bd072df7506") : u"PyGG2 Testing Lobby",
	uuid.UUID("4fd0319b-5868-4f24-8b77-568cbb18fde9") : u"Vanguard Lobby"
}

def htmlprep(utf8string):
    return escape(unicode(utf8string, 'utf8', 'replace'))

class LobbyStatusResource(Resource):
    isLeaf = True
    
    def __init__(self, serverList):
        self.serverList = serverList
        
    def _format_server(self, server):
        passworded = u"X" if server.passworded else u""
        name = htmlprep(server.name)
        map = htmlprep(server.infos["map"]) if "map" in server.infos else u""
        if(server.bots == 0):
            players = u"%u/%u" % (server.players, server.slots)
        else:
            players = u"%u+%u/%u" % (server.players, server.bots, server.slots)
        if("game" in server.infos):
            game = htmlprep(server.infos["game"])
            game += (u" "+htmlprep(server.infos["game_ver"])) if ("game_ver" in server.infos) else u""
            if("game_url" in server.infos):
                game = u'<a href=%s>%s</a>' % (quoteattr(unicode(server.infos["game_url"], 'utf8', 'replace')), game)
        else:
            game = u""
        address = (u"%s:%u" % (socket.inet_ntoa(server.ipv4_endpoint[0]), server.ipv4_endpoint[1])) if server.ipv4_endpoint is not None else u""
        return rowTemplate % (passworded, name, map, players, game, address)
        
    def _format_table(self, lobby):
        if(lobby in knownLobbies):
            lobbyname = escape(knownLobbies[lobby])
        else:
            lobbyname = u'unknown lobby "%s"' % lobby.hex
            
        servers = self.serverList.get_servers_in_lobby(lobby)
        serverRows = u"".join([self._format_server(server) for server in servers])
        
        return tableTemplate % (lobbyname,serverRows)
        
    def render_GET(self, request):
        lobbies = self.serverList.get_lobbies()
        lobbyTables = u"".join([self._format_table(lobby) for lobby in lobbies])
        return (pageTemplate % (lobbyTables,)).encode('utf8', 'replace')
