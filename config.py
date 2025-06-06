import socket
import uuid

# Network ports for lobby protocols and web UI
GG2_PORT = 29942  # Legacy GG2 registration/query
NEWSTYLE_PORT = 29944  # New-style registration/query
WEB_PORT = 29950  # Web status interface

# Banned IP list
BANNED_IP_STRINGS = {"1.2.3.4"}
BANNED_IPS = {socket.inet_aton(ip) for ip in BANNED_IP_STRINGS}

# Flood-control and server expiration durations
SERVER_EXPIRATION_SECS = 70
REGISTRATION_THROTTLE_SECS = 10

# Connection timeouts (used for various protocol operations)
CONNECTION_TIMEOUT_SECS = 5

# Known lobbies for the web interface
KNOWN_LOBBIES = {
    uuid.UUID("1ccf16b1-436d-856f-504d-cc1af306aaa7"): "Gang Garrison Lobby",
    uuid.UUID("0e29560e-443a-93a3-e15e-7bd072df7506"): "PyGG2 Testing Lobby",
    uuid.UUID("4fd0319b-5868-4f24-8b77-568cbb18fde9"): "Vanguard Lobby",
}

