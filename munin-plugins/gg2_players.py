#!/usr/bin/python

from __future__ import with_statement
from contextlib import closing
import socket, uuid, struct, sys

def read_fully(sock, length):
	result = ''
	while(length-len(result) > 0):
		result += sock.recv(length-len(result))
	return result;
		
if(len(sys.argv) > 1 and sys.argv[1] == 'config'):
	print "graph_title GG2 players and available slots"
	print "graph_vlabel count"
	print "players.label players"
	print "slots.label slots"
else:
	LIST_PROTOCOL_ID = uuid.UUID("297d0df4-430c-bf61-640a-640897eaef57")
	GG2_LOBBY_ID = uuid.UUID("1ccf16b1-436d-856f-504d-cc1af306aaa7")

	with closing(socket.create_connection(("127.0.0.1", 29944))) as sock:
		sock.sendall(LIST_PROTOCOL_ID.bytes + GG2_LOBBY_ID.bytes)

		total_playercount = 0
		total_playerslots = 0

		servercount = struct.unpack('>L', read_fully(sock, 4))[0]
		for i in xrange(servercount):
			serverlen = struct.unpack('>L', read_fully(sock, 4))[0]
			serverblock = read_fully(sock, serverlen)
			(serverprotocol, ipv4_port, ipv4_ip, ipv6_port, ipv6_ip, playerslots, playercount, bots, flags, infolen) = struct.unpack(">BH4sH16sHHHHH", serverblock[:35])
			
			total_playercount += playercount
			total_playerslots += playerslots
			
	print "players.value %s" % (total_playercount,)
	print "slots.value %s" % (total_playerslots,)
	
