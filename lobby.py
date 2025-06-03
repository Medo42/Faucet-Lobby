import twisted.web.server
import twisted.web.static
from twisted.internet import reactor

from server import GameServerList
from protocols.gg2 import GG2LobbyRegV1, GG2LobbyQueryV1Factory
from protocols.newstyle import NewStyleReg, NewStyleListFactory
import weblist

serverList = GameServerList()
reactor.listenUDP(29942, GG2LobbyRegV1(serverList))
reactor.listenUDP(29944, NewStyleReg(serverList))
reactor.listenTCP(29942, GG2LobbyQueryV1Factory(serverList))
reactor.listenTCP(29944, NewStyleListFactory(serverList))

webres = twisted.web.static.File("httpdocs")
webres.putChild(b"status", weblist.LobbyStatusResource(serverList))

reactor.listenTCP(29950, twisted.web.server.Site(webres))
reactor.run()
