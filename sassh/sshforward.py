#!/usr/bin/env python
# -*- coding: utf-8 -*-

import socket
import select
import SocketServer
import threading
import errno
from timeout import timeout

g_verbose = False


class ForwardServer (SocketServer.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True


class Handler (SocketServer.BaseRequestHandler):

    def handle(self):

        try:
            chan = self.ssh_transport.open_channel('direct-tcpip',
                                                   (self.chain_host, self.chain_port),
                                                   self.request.getpeername())
        except Exception, e:
            verbose('Incoming request to %s:%d failed: %s' % (self.chain_host,
                                                              self.chain_port,
                                                              repr(e)))
            return
        if chan is None:
            verbose('Incoming request to %s:%d was rejected by the SSH server.' %
                    (self.chain_host, self.chain_port))
            return

        verbose('Connected!  Tunnel open %r -> %r -> %r' % (self.request.getpeername(),
                                                            chan.getpeername(), (self.chain_host, self.chain_port)))
        while True:
            r, w, x = select.select([self.request, chan], [], [])
            if self.request in r:
                try:
                    data = self.request.recv(1024)
                except IOError, e:
                    if e.errno == errno.ECONNRESET: # Connection reset by peer
                        break
                    raise
                if len(data) == 0:
                    break
                try:
                    chan.send(data)
                except: # Ignore errors sending to the proxy process
                    pass
            if chan in r:
                data = chan.recv(1024)
                if len(data) == 0:
                    break
                try:
                    self.request.send(data)
                except IOError, e:
                    if e.errno != errno.ECONNRESET:
                        raise
        try:
            chan.close()
        except EOFError:
            pass # Already closed
        self.request.close()


class FordwardTunnel (threading.Thread):

    def __init__(self, local_port, remote_host, remote_port, transport):
        self.assigned_port = None
        self.local_port = local_port
        self.remote_host = remote_host
        self.remote_port = remote_port
        self.transport = transport
        self.server = None
        threading.Thread.__init__(self)

    def run(self):
            # this is a little convoluted, but lets me configure things for the Handler
            # object.  (SocketServer doesn't give Handlers any way to access the outer
            # server normally.)
            class SubHander (Handler):
                    chain_host = self.remote_host
                    chain_port = self.remote_port
                    ssh_transport = self.transport
            retry_count = 3
            while retry_count > 0:
                    try:
                            self.server = ForwardServer(('', self.local_port), SubHander)
                    except socket.error as err:
                            if err.errno == 98:
                                    print "Trying next port"
                                    pass
                            else:
                                    raise
                    else:
                                    break
                    retry_count -= 1
                    self.local_port += 1
            if retry_count == 0:
                    self.assigned_port = 0
            else:
                    self.assigned_port = self.local_port
                    self.server.serve_forever()

    def shutdown(self):
        if self.server:
            self.server.shutdown()


def verbose(s):
    if g_verbose:
        print s
