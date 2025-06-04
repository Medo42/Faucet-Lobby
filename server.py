"""Game server data structures used by the lobby."""

from __future__ import annotations

import socket
from dataclasses import dataclass, field
from typing import Dict, Optional, Iterable
import uuid

import config
from expirationset import expirationset


@dataclass(eq=False)
class GameServer:
    """Information about a single registered game server."""

    server_id: uuid.UUID
    lobby_id: uuid.UUID
    protocol: int = 0  # 0 = TCP, 1 = UDP
    ipv4_endpoint: Optional[tuple[bytes, int]] = None  # Tuple: (ipv4, port)
    ipv6_endpoint: Optional[tuple[bytes, int]] = None  # Tuple: (ipv6, port)
    name: bytes = b""
    slots: int = 0
    players: int = 0
    bots: int = 0
    passworded: bool = False
    infos: Dict[bytes, bytes] = field(default_factory=dict)

    def __hash__(self) -> int:
        return id(self)

    def __repr__(self):
        retstr = (
            "<GameServer, name="
            + self.name.decode("utf-8", "replace")
            + ", lobby_id="
            + str(self.lobby_id)
        )
        if self.ipv4_endpoint is not None:
            anonip = self.ipv4_endpoint[0][:-1] + b"\0"
            retstr += (
                ", ipv4_endpoint="
                + socket.inet_ntoa(anonip)
                + ":"
                + str(self.ipv4_endpoint[1])
            )
        if self.ipv6_endpoint is not None:
            anonip = (self.ipv6_endpoint[0][:-10] + b"\0" * 10, self.ipv6_endpoint[1])
            retstr += ", ipv6_endpoint=" + str(anonip)
        return retstr + ">"


class GameServerList:
    """Collection of active ``GameServer`` entries with automatic expiry."""

    def __init__(self, duration: int = config.SERVER_EXPIRATION_SECS):
        self._expirationset = expirationset(duration, self._remove_callback)
        self._server_id_dict: Dict[uuid.UUID, GameServer] = {}
        self._endpoint_dict: Dict[tuple[bytes, int], uuid.UUID] = {}
        self._lobby_dict: Dict[uuid.UUID, set[GameServer]] = {}

    def _remove_callback(self, server_id: uuid.UUID, expired: bool) -> None:
        server = self._server_id_dict.pop(server_id)
        if server.ipv4_endpoint is not None:
            del self._endpoint_dict[server.ipv4_endpoint]
        if server.ipv6_endpoint is not None:
            del self._endpoint_dict[server.ipv6_endpoint]
        lobbyset = self._lobby_dict[server.lobby_id]
        lobbyset.remove(server)
        if not lobbyset:
            del self._lobby_dict[server.lobby_id]

    def put(self, server: GameServer) -> None:
        self._expirationset.cleanup_stale()
        if (
            server.ipv4_endpoint in self._endpoint_dict
            and self._endpoint_dict[server.ipv4_endpoint] != server.server_id
            or server.ipv6_endpoint in self._endpoint_dict
            and self._endpoint_dict[server.ipv6_endpoint] != server.server_id
        ):
            print(
                "Server " + str(server) + " rejected - wrong ID for existing endpoint."
            )
            return
        try:
            oldserver = self._server_id_dict[server.server_id]
            if server.ipv4_endpoint is None:
                server.ipv4_endpoint = oldserver.ipv4_endpoint
            if server.ipv6_endpoint is None:
                server.ipv6_endpoint = oldserver.ipv6_endpoint
        except KeyError:
            pass

        self._expirationset.discard(server.server_id)
        self._server_id_dict[server.server_id] = server
        if server.ipv4_endpoint:
            self._endpoint_dict[server.ipv4_endpoint] = server.server_id
        if server.ipv6_endpoint:
            self._endpoint_dict[server.ipv6_endpoint] = server.server_id
        self._lobby_dict.setdefault(server.lobby_id, set()).add(server)
        self._expirationset.add(server.server_id)

    def remove(self, server_id: uuid.UUID) -> None:
        self._expirationset.discard(server_id)

    def get_servers_in_lobby(self, lobby_id: uuid.UUID) -> set[GameServer]:
        self._expirationset.cleanup_stale()
        try:
            return self._lobby_dict[lobby_id].copy()
        except KeyError:
            return set()

    def get_lobbies(self) -> Iterable[uuid.UUID]:
        return self._lobby_dict.keys()
