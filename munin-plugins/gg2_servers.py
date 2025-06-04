#!/usr/bin/python3

import sys

from gg2_common import query_lobby_stats

if len(sys.argv) > 1 and sys.argv[1] == "config":
    print("graph_title Registered GG2 servers")
    print("graph_vlabel servers")
    print("servers.label servers")

else:
    servercount, _, _ = query_lobby_stats()

    print("servers.value %s" % (servercount,))
