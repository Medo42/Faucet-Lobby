#!/usr/bin/python3

import sys

from gg2_common import query_lobby_stats

if(len(sys.argv) > 1 and sys.argv[1] == 'config'):
	print("graph_title GG2 players and available slots")
	print("graph_vlabel count")
	print("players.label players")
	print("slots.label slots")
else:
        _, total_playercount, total_playerslots = query_lobby_stats()

        print("players.value %s" % (total_playercount,))
        print("slots.value %s" % (total_playerslots,))
	
