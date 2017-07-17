#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import sys
import os
import paramiko
import select
import termios
import tty
import time
import signal
import socket
import fcntl
import errno
import logging

from os.path import join, isdir, exists, basename, expanduser
from array import array
from random import randint, choice
from sassh.sshforward import FordwardTunnel
from sassh.randompass import mkpasswd
from sassh.timeout import timeout
from sassh.string import LETTERS


class SSHClient():
    """
    Encapsulates an ssh client connection and integratted with the password
    manager.
    """

    def __init__(self, connection, library):
        self.connection = connection
        self.library = library
        self.new_password = None # To be filled by CTRL-N
        self.recv_lcount = 0 # Quick for .hushlogin
        self.chan = None
        self.chan_log_file = None

        self.verbose = True
        self.ssh = ssh = paramiko.SSHClient()
        self.tunnel = None
        self.ssh_tunnel = self.ssh_tunnel_port = None
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        logger = logging.getLogger("paramiko.transport")
        # Set transport logging to fatal
        ch = logging.StreamHandler()
        logger.addHandler(ch)
        logger.setLevel(logging.FATAL)
        #paramiko.util.log_to_file('/tmp/shell.log')
        #paramiko.common.logging.basicConfig(level=paramiko.common.DEBUG)


    def log(self, message):
        """ print message to screen ig verbose is enabled """
        if self.verbose:
            print message

    def chan_log(self, message):
        if self.chan_log_file:
            self.chan_log_file.write(message)

    #@timeout(60)
    def connect(self):
        """ Establish the connection """
        ssh = self.ssh
        port = 22
        if self.connection.step_stone:
            connection = self.library.getbyname(self.connection.step_stone)
        else:
            connection = self.connection

        while True: # Connection loop for the stetting stone case
            password = connection.password
            username, hostname = connection.url.split('@')
            if self.tunnel: # Connecting to stepping stone tunnel
                hostname = 'localhost'
                port = self.tunnel.local_port
                self.log("*** Using stepping stone %s:%s" % (hostname, port))
            elif ':' in hostname:
                hostname, port = hostname.split(':')
            self.log("*** Connecting to '%s' [%s]" % (connection.name, connection.url))
            try:
                look_for_keys = connection.use_key
                ssh.connect(hostname, port = port
                            , look_for_keys=look_for_keys,  allow_agent=look_for_keys
                            , username=username, password=password, timeout=30)
            finally:
                if self.tunnel:
                    self.tunnel.shutdown()

            h, w = 25, 80
            try:
                h , w = array('h', fcntl.ioctl(sys.stdin, termios.TIOCGWINSZ, '\0'*8))[:2]
            except IOError as e:
                if e.errno not in (errno.EINVAL, errno.ENOTTY):
                    raise
            self.chan = chan = ssh.invoke_shell(
                term=os.getenv('TERM') or 'vt100', width=w, height=h)
            chan.transport.set_keepalive(10)
            chan.settimeout(30)
            self._wait_for_data(["Last login", '[@#$:>]'], verbose=self.verbose)
            #self.log("*** Connection established")
            if self.connection.step_stone and not self.tunnel:
                connection = self.connection
                username, hostname = connection.url.split('@')
                if ':' in hostname:
                    hostname, remote_port = hostname.split(':')
                else:
                    remote_port = 22
                self._set_ssh_tunnel(hostname, int(remote_port))
            else:
                break

        # If the logging dir exists, set the logfile
        logs_dir = expanduser(join('~', 'sassh_logs'))
        if exists(logs_dir):
            sub_logs_dir = join(logs_dir, connection.name)
            if not exists(sub_logs_dir):
                os.mkdir(sub_logs_dir)
            time_fn  = time.strftime("%Y%m%d.%H%M%S.")+str(os.getpid())+".log"
            log_fn = join(sub_logs_dir, time_fn)
            self.chan_log_file = open(log_fn, 'w', 1)


    def interactive_shell(self):
        chan = self.chan
        signal.signal(signal.SIGWINCH, self.sigwinch_passthrough)
        oldtty = termios.tcgetattr(sys.stdin)
        ctrl_x = False

        try:
            tty.setraw(sys.stdin.fileno())
            tty.setcbreak(sys.stdin.fileno())
            chan.settimeout(0.0)
            # set stdin to non blocking, read multiple chars (paste)
            stdin_fd = sys.stdin
            fl = fcntl.fcntl(stdin_fd, fcntl.F_GETFL)
            fcntl.fcntl(stdin_fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
            while True:
                try:
                    r, w, e = select.select([chan, sys.stdin], [], [])
                except select.error, e: # don't raise on sigwinch
                    if e.args[0] != errno.EINTR:
                        raise
                if chan in r:
                    try:
                        x = chan.recv(1024)
                        sys.stdout.flush()
                        if len(x) == 0:
                            break
                        self.chan_log(x)
                        while True:
                            try:
                                sys.stdout.write(x)
                            # Large chunks of output can generate errno.EAGAIN
                            except IOError, e:
                                if e.errno == errno.EAGAIN:
                                    pass
                            else:
                                sys.stdout.flush()
                                break
                    except socket.timeout:
                        pass

                if sys.stdin in r:
                        while True:
                            try:
                                x = sys.stdin.read(4096)
                            except IOError, e:
                                if e.errno == errno.EAGAIN:
                                    pass
                            else:
                                break
                        if len(x) == 0:
                            break
                        #self.chan_log(x)
                        if len(x) == 1:
                            if ctrl_x and x[0].lower() == 'p':
                                password = self.connection.password
                                self.sendall(password+"\n")
                                ctrl_x = False
                                continue
                            if ctrl_x and x[0].lower() == 'n':
                                if not self.new_password:
                                    self.new_password = mkpasswd()
                                self.sendall(self.new_password+"\n")
                                ctrl_x = False
                                continue
                            ctrl_x = (ord(x[0]) == 24) # CTRL-X
                        if not ctrl_x:
                            self.sendall(x)

        finally:
            # Restore terminal settings and reset stdin to blocking
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, oldtty)
            stdin_fd = sys.stdin
            fl = fcntl.fcntl(stdin_fd, fcntl.F_GETFL)
            fcntl.fcntl(stdin_fd, fcntl.F_SETFL, fl & ~os.O_NONBLOCK)
        self.log("*** Connection to '%s' was terminated\r" % self.connection.name)
        if self.new_password:
            print("*** A new password was generated during the SSH session.")
            response = ''
            while response not in ['Y', 'N']:
                print("*** Update the password for %s with the new value (Y/N)? " % self.connection.url),
                response = sys.stdin.read(1).upper()
                print("")
                if response == 'Y':
                    self.connection.password = self.new_password
                    self.library.save(self.connection)
                    print "New password saved."
        if self.tunnel:
            self.tunnel.shutdown()

    # SIGWINCH needs to be send to the child when the parent is resized
    def sigwinch_passthrough (self, sig, data):
        signal.signal(signal.SIGWINCH, signal.SIG_IGN)        
        h , w = array('h', fcntl.ioctl(sys.stdin,termios.TIOCGWINSZ,'\0'*8))[:2]
        self.chan.resize_pty(w, h)
        signal.signal(signal.SIGWINCH, self.sigwinch_passthrough)
        return True

    @timeout(120)
    def _wait_for_data(self, options, verbose=False):
        chan = self.chan
        data = ""
        while True:
            x = chan.recv(1024)
            self.recv_lcount += x.count('\n')
            if len(x) == 0:
                self.log( "*** Connection terminated\r")
                sys.exit(3)
            self.chan_log(x)
            data += x
            if verbose:
                sys.stdout.write(x)
                sys.stdout.flush()
            for i in range(len(options)):
                if re.search(options[i], data):
                    return i
        return -1

    @timeout(30)
    def _wait_for_line_data(self, end_of_data):
        data = ""
        while True:
            x = self.chan.recv(1024)
            if len(x) == 0:
                self.log( "*** Connection terminated\r")
                sys.exit(3)
            self.chan_log(x)
            data += x
            lines = data.split("\n")[:-1] # last line may not been terminated
            data = data.split("\n")[-1]
            for line in lines:
                if line.strip('\r').endswith(end_of_data):
                    return
                print line


    def sendall(self, message):
        self.chan.sendall(message)

    @timeout(20)
    def _set_ssh_tunnel(self, hostname, remote_port=22):
        tunnel_port = randint(2000, 40000)
        self.tunnel = tunnel = FordwardTunnel(tunnel_port, hostname, remote_port, self.ssh.get_transport())
        tunnel.start()
        tunnel_port = None
        while tunnel_port is None:
            time.sleep(10/1000.0)
            tunnel_port = tunnel.local_port
        self.log("*** SSH tunnel setup at %s:%s" % (hostname, tunnel.local_port))

    @timeout(30)
    def perform_sudo(self):
        self.sendall("sudo -K\n")
        self.sendall("sudo su - -s /bin/bash\n")
        rc = self._wait_for_data(['[P|p]assword'], verbose=False)
        password = self.connection.password
        self.sendall(password+"\n")
        # Critical sync point, we must receive a prompt before resuming
        self._wait_for_data(['[@#$:>]'])

    def get_file(self, remote_file):
        sftp = paramiko.SFTPClient.from_transport(self.chan.transport)
        local_fname = basename(remote_file)
        sftp.get(remote_file, local_fname)

    def put_file(self, remote_file):
        local_fname, remote_dir = remote_file.split(':')
        sftp = paramiko.SFTPClient.from_transport(self.chan.transport)
        sftp.put(local_fname, join(remote_dir, basename(local_fname)))

    def run_command(self, command):
        self.sendall('stty -echo\n')
        self.sendall('export PS1=""\n')
        self.sendall('echo "Just" "Randomsassh"\n')
        self._wait_for_data(["Just Randomsassh"], verbose=False)
        self.sendall(command+"\n")
        eoc_string = 'sassh_'+''.join([choice(LETTERS) for _ in range(50)])
        self.sendall('echo '+eoc_string+'\n')
        self._wait_for_line_data(eoc_string)
        if self.tunnel:
            self.tunnel.shutdown()

    def run_su_script(self, run_specification):
        if ':' in run_specification:
            local_script_fname, local_output_dir = run_specification.split(':')
            if not isdir(local_output_dir):
                sys.stderr.write("ERROR: Output directory %s for -R must exist!\n" % local_output_dir)
                sys.exit(9)
        else:
            local_script_fname = run_specification
            local_output_dir = None
        connection = self.connection
        username, host = connection.url.split('@')
        tmp_fname = join('/tmp', "%s_%d_%d"
            % (username, os.getpid(), randint(1, 9999)))
        sftp = paramiko.SFTPClient.from_transport(self.chan.transport)
        sftp.put(local_script_fname, tmp_fname)
        sftp.chmod(tmp_fname, 0700)
        self.sendall("sudo -K\n")
        self.sendall("sudo su -\n")
        self._wait_for_data(['[P|p]assword'])
        self.sendall(connection.password+"\n")
        # Critical sync point, we must receive a prompt before resuming
        self._wait_for_data(['[@#$:>]'])
        self.sendall("%s > %s.out 2>&1\n" %
            (tmp_fname, tmp_fname))
        self.sendall("chown %s %s.out\n" % (username, tmp_fname))
        self.sendall('echo "Just" "Randomsassh"\n')
        self._wait_for_data(["Just Randomsassh"])
        local_fname = join(local_output_dir or '/tmp', connection.name)
        sftp.get(tmp_fname+'.out', local_fname)
        self.sendall('rm -f %s %s ' % (tmp_fname, tmp_fname+'.out\n'))
        if not local_output_dir:
            sys.stdout.write(open(local_fname).read())
