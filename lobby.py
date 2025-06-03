import twisted.web.server
import twisted.web.static
from twisted.internet import reactor
import config

from server import GameServerList
from protocols.gg2 import GG2LobbyRegV1, GG2LobbyQueryV1Factory
from protocols.newstyle import NewStyleReg, NewStyleListFactory
import weblist

serverList = GameServerList()
reactor.listenUDP(config.GG2_PORT, GG2LobbyRegV1(serverList))
reactor.listenUDP(config.NEWSTYLE_PORT, NewStyleReg(serverList))
reactor.listenTCP(config.GG2_PORT, GG2LobbyQueryV1Factory(serverList))
reactor.listenTCP(config.NEWSTYLE_PORT, NewStyleListFactory(serverList))

webres = twisted.web.static.File("httpdocs")
webres.putChild(b"status", weblist.LobbyStatusResource(serverList))

reactor.listenTCP(config.WEB_PORT, twisted.web.server.Site(webres))
reactor.run()
