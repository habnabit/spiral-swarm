import os

from twisted.internet import defer, protocol
from twisted.protocols.basic import LineReceiver
from twisted.protocols.stateful import StatefulProtocol


class FileSenderProtocol(StatefulProtocol):
    concurrency = 5

    def connectionMade(self):
        # bogus
        self.transport.disconnecting = False
        self.deferred = defer.Deferred()
        basename = os.path.basename(self.factory.filename)
        self.length = os.path.getsize(self.factory.filename)
        self.transport.write(basename + '\0')
        self.transport.write(self.factory.hostname + '\0')
        self.transport.write(str(self.length) + '\0')

    def getInitialState(self):
        return self.checkOK, 2

    def checkOK(self, data):
        if data != 'OK':
            self.transport.loseConnection()
        self.beginWritingFile()

    def beginWritingFile(self):
        self.factory.interface.startedSending(self.length)
        self.infile = open(self.factory.filename, 'rb')
        self.sent = 0
        for x in xrange(self.concurrency):
            self.writeChunk()
            if self.infile is None:
                break

    def writeChunk(self, ign=None):
        if self.infile is None:
            return
        chunk = self.infile.read(4096)
        if not chunk:
            self.transport.loseConnection()
            self.infile.close()
            self.infile = None
            return
        d = self.transport.write(chunk)
        d.addCallback(self.writeChunk)
        self.sent += len(chunk)
        self.factory.interface.progressAt(self.sent)

    def readConnectionLost(self):
        pass

    def connectionLost(self, reason):
        self.deferred.errback(reason)


class FileSenderFactory(protocol.Factory):
    protocol = FileSenderProtocol

    def __init__(self, filename, hostname, interface):
        self.filename = filename
        self.hostname = hostname
        self.interface = interface


class FileReceiverProtocol(LineReceiver):
    delimiter = '\0'

    def connectionMade(self):
        # totally bogus
        self.transport.disconnecting = False
        self.deferred = defer.Deferred()
        self.lineReceived = self.gotFilename

    def gotFilename(self, filename):
        self.filename = filename
        self.lineReceived = self.gotHostname

    def gotHostname(self, hostname):
        self.hostname = hostname
        self.lineReceived = self.gotLength

    def gotLength(self, length):
        self.length = int(length)
        self.received = 0
        peer = self.transport.getPeer()
        self.setRawMode()
        self.factory.interface.gotSender(
            self.filename, self.length, self.hostname, peer.longTermKey, self)

    def sendOK(self):
        self.transport.write('OK\0')
        self.outfile = open(self.factory.filename, 'wb')

    def rawDataReceived(self, data):
        self.received += len(data)
        self.factory.interface.progressAt(self.received)
        self.outfile.write(data)

    def readConnectionLost(self):
        self.transport.loseConnection()
        self.outfile.close()

    def connectionLost(self, reason):
        self.deferred.errback(reason)


class FileReceiverFactory(protocol.Factory):
    protocol = FileReceiverProtocol

    def __init__(self, filename, interface):
        self.filename = filename
        self.interface = interface
