from contextlib import closing
import socket
import uuid
import struct
import os
import sys

# Ensure repository root is on path to import config
sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(__file__)), ".."))
import config


def read_fully(sock, length):
    """Read exactly *length* bytes from *sock*."""
    result = b''
    while len(result) < length:
        chunk = sock.recv(length - len(result))
        if not chunk:
            raise ConnectionError("Socket closed unexpectedly")
        result += chunk
    return result


def query_lobby_stats():
    """Return (servercount, total_players, total_slots) from lobby."""
    LIST_PROTOCOL_ID = uuid.UUID("297d0df4-430c-bf61-640a-640897eaef57")
    GG2_LOBBY_ID = uuid.UUID("1ccf16b1-436d-856f-504d-cc1af306aaa7")

    with closing(socket.create_connection(("127.0.0.1", config.NEWSTYLE_PORT))) as sock:
        sock.sendall(LIST_PROTOCOL_ID.bytes + GG2_LOBBY_ID.bytes)

        servercount = struct.unpack('>L', read_fully(sock, 4))[0]
        total_playercount = 0
        total_playerslots = 0
        for _ in range(servercount):
            serverlen = struct.unpack('>L', read_fully(sock, 4))[0]
            serverblock = read_fully(sock, serverlen)
            (
                _protocol,
                _ipv4_port,
                _ipv4_ip,
                _ipv6_port,
                _ipv6_ip,
                playerslots,
                playercount,
                _bots,
                _flags,
                _infolen,
            ) = struct.unpack(
                ">BH4sH16sHHHHH", serverblock[:35]
            )
            total_playercount += playercount
            total_playerslots += playerslots

    return servercount, total_playercount, total_playerslots
