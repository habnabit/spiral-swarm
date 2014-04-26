import fish
from spiral import dnscurve
from twisted.internet import defer
from twisted.protocols.basic import LineOnlyReceiver
from twisted.python import log


def formatKey(key):
    key = dnscurve.DNSCurveBase32Encoder.encode(str(key))
    return '-'.join(key[i:i+13] for i in xrange(0, 52, 13))


class SenderInterface(LineOnlyReceiver):
    delimiter = '\n'

    def __init__(self, key):
        self.key = key
        self.seenHosts = set()
        self.hostInfo = {}
        self.deferred = defer.Deferred()

    def connectionMade(self):
        self.sendLine('your key is: ' + formatKey(self.key))
        self.sendLine('pick a host to send to:')

    def gotReceiver(self, hostname, port, key, address):
        host = hostname, str(key)
        if host in self.seenHosts:
            return
        self.seenHosts.add(host)
        index = len(self.seenHosts)
        self.hostInfo[index] = hostname, port, key, address
        self.sendLine('%s: %s (key %s)' % (index, hostname, formatKey(key)))

    def lineReceived(self, line):
        try:
            self._lineReceived(line)
        except Exception:
            log.err(None, 'error parsing sender input')

    def _lineReceived(self, line):
        if self.deferred is None:
            return
        index = int(line.strip())
        self.deferred, d = None, self.deferred
        d.callback(self.hostInfo[index])

    def startedSending(self, length):
        self.fish = fish.ProgressFish(total=length, outfile=self.transport)

    def progressAt(self, received):
        self.fish.animate(amount=received)


class ReceiverInterface(LineOnlyReceiver):
    delimiter = '\n'

    def __init__(self, key):
        self.key = key
        self.seenHosts = set()
        self.hostInfo = {}
        self.deferred = defer.Deferred()

    def connectionMade(self):
        self.sendLine('your key is: ' + formatKey(self.key))
        self.sendLine('pick a host to receive from:')

    def gotSender(self, filename, length, hostname, key, protocol):
        host = filename, hostname
        if host in self.seenHosts:
            return
        self.seenHosts.add(host)
        index = len(self.seenHosts)
        self.hostInfo[index] = host, filename, length, protocol
        self.sendLine('%s: %s (filename %r; length %s; key %s)' % (
            index, hostname, filename, length, formatKey(key)))

    def lineReceived(self, line):
        try:
            self._lineReceived(line)
        except Exception:
            log.err(None, 'error parsing receiver input')

    def _lineReceived(self, line):
        if self.deferred is None:
            return
        index = int(line.strip())
        self.deferred, d = None, self.deferred
        d.callback(self.hostInfo[index])
        self.fish = fish.ProgressFish(total=self.hostInfo[index][2], outfile=self.transport)

    def progressAt(self, received):
        self.fish.animate(amount=received)
