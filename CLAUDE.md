# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is the Faucet Lobby - a game server lobby system originally created for Gang Garrison 2 but designed to be more generic. It's a Python-based server discovery system that allows game servers to register themselves and clients to query for available servers.

## Architecture

The system consists of several key components:

**Core Server Management (`lobby.py`)**:
- `GameServer` class: Represents individual game servers with metadata (name, players, bots, maps, etc.)
- `GameServerList` class: Manages server registration, expiration, and lookup using an expiration set
- Servers auto-expire after 70 seconds unless re-registered every ~30 seconds

**Protocol Handlers**:
- `GG2LobbyRegV1`: Legacy UDP registration protocol for Gang Garrison 2 servers
- `NewStyleReg`: Modern UDP registration protocol supporting new-style server data
- `GG2LobbyQueryV1`: Legacy TCP query protocol for client requests  
- `NewStyleList`: Modern TCP query protocol with structured server data

**Web Interface (`weblist.py`)**:
- `LobbyStatusResource`: HTTP interface showing active servers in browser-friendly format
- Serves at port 29950 with status page at `/status`

**Utilities**:
- `expirationset.py`: Time-based expiration tracking for server entries
- `ordereddict.py`: Ordered dictionary implementation for Python compatibility

**Network Ports**:
- 29942: Legacy GG2 registration (UDP) and query (TCP) 
- 29944: New-style registration (UDP) and query (TCP)
- 29950: Web interface (HTTP)

## Protocol Support

The lobby supports both legacy Gang Garrison 2 protocols and a newer generic protocol defined in "Protocol Spec.txt". The newer protocol uses UUIDs for lobby identification and supports IPv6, structured key-value metadata, and better extensibility.

## Running the Server

Start the lobby server:
```bash
python lobby.py
```

The server uses Twisted framework and will listen on the configured ports. No build or compile step is needed - it's pure Python.

## Key Files

- `lobby.py`: Main server implementation and protocol handlers
- `weblist.py`: Web interface for browser-based server listing  
- `Protocol Spec.txt`: Complete protocol specification for registration and queries
- `expirationset.py`: Auto-expiring data structure for server management
- `httpdocs/`: Static web assets (CSS, etc.)

## Legacy Considerations

The codebase contains special handling for Gang Garrison 2 legacy protocols and should be modularized further. The code was written quickly by someone with limited Python experience, so refactoring opportunities exist.