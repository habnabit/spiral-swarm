from nacl import public
from twisted.internet.protocol import DatagramProtocol
from twisted.internet import task


MULTICAST_GROUP = '224.0.0.153'
MULTICAST_PORT = 11656
MULTICAST_HOST = MULTICAST_GROUP, MULTICAST_PORT


class SwarmScanner(DatagramProtocol):
    def __init__(self, delegate):
        self.delegate = delegate

    def begin(self, reactor):
        self.looper = task.LoopingCall(self.scanForHosts)
        self.looper.clock = reactor
        self.port = reactor.listenMulticast(
            MULTICAST_PORT, self, listenMultiple=True)

    def stop(self):
        self.looper.stop()
        self.port.stopListening()

    def startProtocol(self):
        self.transport.setTTL(5)
        self.transport.joinGroup(MULTICAST_GROUP)
        self.looper.start(5)

    def scanForHosts(self):
        self.transport.write('WHOSTHERE', MULTICAST_HOST)

    def datagramReceived(self, datagram, address):
        if not datagram.startswith('HERE ') or datagram.count(' ') < 3:
            return
        _, hostname, port, key = datagram.split(' ', 3)
        port = int(port)
        key = public.PublicKey(key)
        self.delegate(hostname, port, key, address)


class SwarmBroadcaster(DatagramProtocol):
    def __init__(self, hostname, key, portNumber):
        self.hostname = hostname
        self.key = key
        self.portNumber = portNumber

    def begin(self, reactor):
        self.port = reactor.listenMulticast(
            MULTICAST_PORT, self, listenMultiple=True)

    def stop(self):
        self.port.stopListening()

    def startProtocol(self):
        self.transport.setTTL(5)
        self.transport.joinGroup(MULTICAST_GROUP)
        self.makePresenceKnown()

    def makePresenceKnown(self):
        self.transport.write(
            'HERE %s %s %s' % (self.hostname, self.portNumber, self.key),
            MULTICAST_HOST)

    def datagramReceived(self, datagram, address):
        if datagram != 'WHOSTHERE':
            return
        self.makePresenceKnown()
