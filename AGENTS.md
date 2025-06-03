# AGENTS.md

This file provides guidance to AI development agents working in this repository.

## Project Overview

Faucet Lobby is a Python based lobby server originally created for Gang
Garrison 2 but written to support other games. Game servers register
with the lobby over UDP and clients can query available servers. A small
web interface lists all known servers.

## Architecture

**Core Server Management (`lobby.py`)**
- `GameServer` and `GameServerList` classes manage server metadata and
  registration. Servers expire after 70 seconds unless refreshed about
  every 30 seconds.

**Protocol Handlers**
- `GG2LobbyRegV1` / `GG2LobbyQueryV1`: legacy Gang Garrison 2 UDP and
  TCP protocols.
- `NewStyleReg` / `NewStyleList`: modern UDP registration and TCP query
  protocols using UUIDs and key–value metadata.

**Web Interface (`weblist.py`)**
- `LobbyStatusResource` serves a status page at `/status` on port 29950.

**Utilities**
- `expirationset.py`: auto-expiring data structure used by the server
  list.

## Key Ports
- 29942 – legacy GG2 registration (UDP) and query (TCP)
- 29944 – new-style registration (UDP) and query (TCP)
- 29950 – web interface (HTTP)

## Running the Server
Start the lobby server with:
```bash
python lobby.py
```
The code requires Python 3 and the Twisted framework. Install
dependencies with:
```bash
pip install twisted requests
```

## Testing
Run the integration test suite after making changes:
```bash
python test_integration.py
```
The tests start the server and exercise all registration and query
protocols as well as the web interface.

## Legacy Considerations
Some code still has special cases for Gang Garrison 2. Refactoring into
separate modules would improve maintainability.
