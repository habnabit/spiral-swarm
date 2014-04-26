import argparse
import socket
import sys

from spiral import curvecp, keys
from twisted.internet import defer, stdio, task
from twisted.python import log

from spiralswarm._version import __version__
from spiralswarm import interaction, multicast, transfer


class SpiralSwarm(object):
    _subcommands = {
        'send-file': 'send a file over the LAN',
        'receive-file': 'receive a file from the LAN',
    }

    def startStdio(self, reactor, interface):
        sio = stdio.StandardIO(interface, reactor=reactor)
        sio.flush = lambda: None

        def formatLogEvent(e):
            if 'failure' not in e:
                return
            text = log.textFromEventDict(e)
            sio.write('### ERROR ###\n%s\n' % (text,))

        log.startLoggingWithObserver(formatLogEvent, setStdout=False)

    def send_file_args(self, parser):
        parser.add_argument(
            '-n', '--hostname', default=socket.gethostname(),
            help='the hostname to advertise')
        parser.add_argument('filename', help='the file to send')

    @defer.inlineCallbacks
    def send_file_action(self, reactor, args):
        key = keys.EphemeralKey()
        interface = interaction.SenderInterface(key.key.public_key)
        self.startStdio(reactor, interface)
        scanner = multicast.SwarmScanner(interface.gotReceiver)
        scanner.begin(reactor)
        _, port, server_key, (host, _) = yield interface.deferred
        scanner.stop()
        endpoint = curvecp.CurveCPClientEndpoint(
            reactor, host, port, server_key, clientKey=key)
        proto = yield endpoint.connect(
            transfer.FileSenderFactory(args.filename, args.hostname, interface))
        yield proto.deferred

    def receive_file_args(self, parser):
        parser.add_argument(
            '-n', '--hostname', default=socket.gethostname(),
            help='the hostname to advertise')
        parser.add_argument('filename', help='the file to write to')

    @defer.inlineCallbacks
    def receive_file_action(self, reactor, args):
        key = keys.EphemeralKey()
        interface = interaction.ReceiverInterface(key.key.public_key)
        self.startStdio(reactor, interface)
        endpoint = curvecp.CurveCPServerEndpoint(reactor, 0, key)
        port = yield endpoint.listen(
            transfer.FileReceiverFactory(args.filename, interface))
        port_number = port.getHost().port
        broadcaster = multicast.SwarmBroadcaster(
            args.hostname, key.key.public_key, port_number)
        broadcaster.begin(reactor)
        _, _, _, proto = yield interface.deferred
        proto.sendOK()
        yield proto.deferred

    def build_subcommands(self, action_prefix, subparsers, subcommands):
        for subcommand, subcommand_help in sorted(subcommands.items()):
            subsubcommand = False
            if isinstance(subcommand_help, tuple):
                subcommand_help, subsubcommands = subcommand_help
                subsubcommand = True
            subcommand_method = action_prefix + subcommand.replace('-', '_')
            action_method = getattr(self, '%s_action' % (subcommand_method,))
            subparser = subparsers.add_parser(
                subcommand, help=subcommand_help,
                description=action_method.__doc__)
            args_method = getattr(self, '%s_args' % (subcommand_method,), None)
            if args_method is not None:
                args_method(subparser)

            if subsubcommand:
                subaction_prefix = subcommand_method + '_'
                command = subaction_prefix + 'command'
                subsubparsers = subparser.add_subparsers(dest=command)
                self.build_subcommands(
                    subaction_prefix, subsubparsers, subsubcommands)

    def build_parser(self):
        "Build an ``ArgumentParser`` from the defined subcommands."
        parser = argparse.ArgumentParser(prog='spiral-swarm')
        parser.add_argument('-V', '--version', action='version',
                            version='%(prog)s ' + __version__)
        parser.add_argument('-v', '--verbose', action='store_true',
                            help='increase output on errors')
        subparsers = parser.add_subparsers(dest='command')
        self.build_subcommands('', subparsers, self._subcommands)
        return parser

    def find_action(self, args):
        if not args.command:
            return None
        command = ret = args.command.replace('-', '_')
        while True:
            next_command = command + '_command'
            subcommand = getattr(args, next_command, None)
            if subcommand is None:
                break
            command, ret = (
                next_command, '%s_%s' % (ret, subcommand.replace('-', '_')))
        return ret

    def main(self, args=None):
        parser = self.build_parser()
        args = parser.parse_args(args)
        self.verbose = args.verbose
        action = self.find_action(args)
        if not action:
            parser.print_help()
            sys.exit(2)
        action_method = getattr(self, action + '_action')
        task.react(action_method, [args])


def main():
    SpiralSwarm().main()
