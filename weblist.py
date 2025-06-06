"""HTTP resources for displaying the lobby status page."""

from twisted.web.resource import Resource
from xml.sax.saxutils import escape, quoteattr
import socket
import uuid
import config
from server import GameServer, GameServerList


def page_template(content: str) -> str:
    """Return full HTML page embedding ``content``."""

    return f"""<!doctype html>
<html>
<head>
    <title>Lobby status page</title>
    <meta http-equiv="content-type"
        content="text/html;charset=utf-8" />
    <link rel="stylesheet" type="text/css" href="style.css" />
</head>
<body>
    <img src="forum_logo.gif" alt="" id=smflogo><div id=head><img src="header_logo.png" alt="" id=logo></div>
    {content}
</body>
</html>"""


def table_template(lobbyname: str, rows: str) -> str:
    """Format the table listing all servers for a lobby."""

    return f"""
    <h2>Active servers in the {lobbyname}</h2>
    <div id=desc><p>Game information links are provided by the game servers and are not in any way related to this site. You have been warned.</p></div>
    <table class="serverlist">
        <thead>
            <tr>
                <th class="pw">PW</th>
                <th>Name</th>
                <th>Map</th>
                <th>Players</th>
                <th>Game</th>
                <th>Address</th>
            </tr>
        </thead><tbody>
            {rows}
        </tbody>
    </table>
"""


def row_template(
    passworded: str, name: str, map_: str, players: str, game: str, address: str
) -> str:
    """Create one HTML table row for a server entry."""

    return f"""
                <tr>
                    <td class="pw">{passworded}</td>
                    <td>{name}</td>
                    <td>{map_}</td>
                    <td>{players}</td>
                    <td>{game}</td>
                    <td>{address}</td>
                </tr>
"""


def htmlprep(utf8string: bytes | str) -> str:
    """Escape a UTF-8 byte string or ``str`` for HTML output."""
    if isinstance(utf8string, bytes):
        return escape(utf8string.decode("utf-8", "replace"))
    else:
        return escape(utf8string)


class LobbyStatusResource(Resource):
    isLeaf = True

    def __init__(self, serverList: "GameServerList") -> None:
        """Create a status page serving the contents of ``serverList``."""

        self.serverList = serverList

    def _format_server(self, server: "GameServer") -> str:
        """Return an HTML table row for ``server``."""
        passworded = "X" if server.passworded else ""
        name = htmlprep(
            server.name.decode("utf-8", "replace")
            if isinstance(server.name, bytes)
            else server.name
        )
        map_ = (
            htmlprep(server.infos[b"map"].decode("utf-8", "replace"))
            if b"map" in server.infos
            else ""
        )
        if server.bots == 0:
            players = f"{server.players}/{server.slots}"
        else:
            players = f"{server.players}+{server.bots}/{server.slots}"
        if b"game" in server.infos:
            game = htmlprep(server.infos[b"game"].decode("utf-8", "replace"))
            if b"game_ver" in server.infos:
                game += " " + htmlprep(
                    server.infos[b"game_ver"].decode("utf-8", "replace")
                )
            if b"game_url" in server.infos:
                url = quoteattr(server.infos[b"game_url"].decode("utf-8", "replace"))
                game = f"<a href={url}>{game}</a>"
        else:
            game = ""
        address = (
            f"{socket.inet_ntoa(server.ipv4_endpoint[0])}:{server.ipv4_endpoint[1]}"
            if server.ipv4_endpoint is not None
            else ""
        )
        return row_template(passworded, name, map_, players, game, address)

    def _format_table(self, lobby: uuid.UUID) -> str:
        """Return a full HTML table listing servers for ``lobby``."""
        if lobby in config.KNOWN_LOBBIES:
            lobbyname = escape(config.KNOWN_LOBBIES[lobby])
        else:
            lobbyname = f'unknown lobby "{lobby.hex}"'

        servers = self.serverList.get_servers_in_lobby(lobby)
        serverRows = "".join([self._format_server(server) for server in servers])

        return table_template(lobbyname, serverRows)

    def render_GET(self, request):
        lobbies = self.serverList.get_lobbies()
        lobbyTables = "".join([self._format_table(lobby) for lobby in lobbies])
        return page_template(lobbyTables).encode("utf8", "replace")
