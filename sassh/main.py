#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
import socket
import errno
from getpass import getpass
from optparse import OptionParser
from sassh.connectionlib import Library, Connection
from sassh.sshclient import SSHClient
from paramiko import SSHException

try:
    import pygtk
    pygtk.require('2.0')
    import gtk
    GTK_AVAILABLE = True
except ImportError:
    GTK_AVAILABLE = False

class Main():
    """ Main class for the application """

    def __init__(self):
        self._get_sassh_gpg_pub_key()
        self.host_library = Library('sassh', self.sassh_gpg_pub_key)
        self.options = self.args = None
        self.sassh_gpg_pub_key = None

    def parse_args(self):
        """ Parse command line arguments """
        parser = OptionParser()
        parser.add_option("-a", "--add-connection",
                          action="store", type="string", dest="add_connection",
                          help="Add connection to the configuration database")
        parser.add_option("-d", "--del-connection",
                          action="store_true", dest="del_connection",
                          help="Delete host from the configuration database")
        parser.add_option("-g", "--get",
                          action="store", type="string", dest="get_file",
                          help="Get file from server")
        parser.add_option("--put",
                          action="store", type="string", dest="put_file",
                          help="Put file from server")
        parser.add_option("-k", "--use-key",
                          action="store_true", dest="set_use_key",
                          help="Set connection to use key based authentication")
        parser.add_option("-l", "--list",
                          action="store_true", dest="list",
                          help="List configured connections names")
        parser.add_option("-L", "--long-list",
                          action="store_true", dest="long_list",
                          help="List configured connections (with details)")
        parser.add_option("-p", "--set-password",
                          action="store", type="string", dest="set_password",
                          help="Set connection password")
        parser.add_option("-r", "--run",
                          action="store", type="string", dest="run_command",
                          help="Run command and exit")
        parser.add_option("-R", "--run-su",
                          action="store", type="string", dest="run_su_script",
                          help="Run script with super user privileges")
        parser.add_option("--reset",
                          action="store_true", dest="reset",
                          help="Change password for connection")
        parser.add_option("-s", "--set-connection",
                          action="store", type="string", dest="set_connection",
                          help="Set login information for connection")
        parser.add_option("-S", "--set-step-stone",
                          action="store", type="string", dest="set_step_stone",
                          help="Set stepping stone connection")
        parser.add_option("-t", "--change-tags",
                          action="store", type="string", dest="change_tags",
                          help="Change connection tags")
        parser.add_option("--super",
                          action="store_true", dest="super",
                          help="Perform 'sudo su -' after logging in")
        parser.add_option("-w", "--show-connection",
                          action="store_true", dest="show_connection",
                          help="Show connection information")
        self.options, self.args = parser.parse_args()

    def _get_sassh_gpg_pub_key(self):
        """ Check that the environment variable SASSH_GPG_PUB_KEY is defined """
        sassh_gpg_pub_key = os.getenv('SASSH_GPG_PUB_KEY')
        if not sassh_gpg_pub_key:
            print """
sassh uses a GPG encrypted file to store connection passwords.
You must generate a GPG keypair with "gpg --gen-key" .
YOU SHOULD PROTECT THEY KEY WITH A PASSPHRASE .
Then set your shell's SASSH_GPG_PUB_KEY variable to to the public id as
displayed from "gpg --list-keys", e.g: pub   4096R/7FD63AB0
    export SASSH_GPG_PUB_KEY="7FD63AB0"
"""
            sys.exit(1)
        self.sassh_gpg_pub_key = sassh_gpg_pub_key


    def _list_connections(self, pattern, long_list):
        """ List all the configured connections """
        library = self.host_library
        for connection_name in library.connections:
            connection = None
            if pattern and pattern[0] == '+':
                connection = library.getbyname(connection_name)
                if not connection.tags or pattern not in connection.tags:
                    continue
            else:
                if not connection_name.lower().startswith(pattern.lower()):
                    continue
            if long_list:
                connection = connection or library.getbyname(connection_name)
                show_fields = connection.name+" "
                show_fields += "-a "+connection.url+" "
                if connection.use_key:
                    show_fields += "-k "
                if connection.step_stone:
                    show_fields += "-S "+connection.step_stone+" "
                if connection.tags and len(connection.tags) > 1:
                    show_fields += "-t "+connection.tags
                print show_fields
            else:
                print connection_name
        sys.exit(0)

    def _process_args(self):
        """ Return connection definition after processing cmd arguments  """

        options, args = self.options, self.args
        # Check connection availability and management options
        if len(args) < 1 and not (options.list or options.long_list):
            print "Usage:"
            print "  %s connection_name [options]" % sys.argv[0]
            print "  %s --list" % sys.argv[0]
            sys.exit(2)

        library =  self.host_library

        if (options.list or options.long_list):
            pattern = args[0] if len(args) > 0 else ''
            self._list_connections(pattern, options.long_list)

        connection_name = args[0].lower()

        if options.set_step_stone:
            try:
                library.getbyname(options.set_step_stone)
            except IOError:
                print 'No connection with name %s !' % options.set_step_stone
                sys.exit(4)
        try:
            connection = library.getbyname(connection_name)
        except IOError:
            if not options.add_connection:
                print 'No connection with name %s !' % connection_name
                print 'If you want to add it use "--add-connection"'
                sys.exit(3)
            else:
                connection = Connection(connection_name)
        else:
            if options.add_connection:
                print "Connection with name %s is already stored!" % \
                    connection_name
                sys.exit(4)
            if options.del_connection:
                library.remove(connection)
                sys.exit(0)
            if options.show_connection:
                print "URL", connection.url
                if GTK_AVAILABLE:
                    show_password = '(Copied to th clipboard)'
                    clipboard = gtk.clipboard_get()
                    clipboard.set_text(connection.password)
                    clipboard.store()
                else:
                    show_password = connection.password
                print "PASSWORD", show_password
                if connection.use_key:
                    print "USING KEY"
                print connection.tags or '+'
                sys.exit(0)
            if options.reset:
                options.set_connection = connection.url
                options.password = None
            if options.change_tags:
                if options.change_tags[0] != '+':
                    print "Tags format is: +tag1+tag2...+tagN"
                    sys.exit(4)
                connection.change_tags(options.change_tags)


        if  options.set_step_stone:
            connection.step_stone = options.set_step_stone

        if options.set_password:
            if options.set_use_key:
                sys.stderr.write('You are already setting to key authentication!\n')
                sys.exit(5)
            else:
                connection.use_key = False
                connection.password = options.set_password

        if options.set_use_key:
            connection.use_key = True

        # Ask for login password if setting a connection url
        new_connection_url = options.add_connection or options.set_connection
        if new_connection_url:
            connection.url = new_connection_url
            if not connection.password and not connection.use_key:
                options.set_password = True
                while True:
                    print "Type the password for connection %s [%s]: " \
                        % (connection_name, connection.url)
                    password1 = getpass()
                    if len(password1) < 1:
                        print "Password must be at least 1 chars long!"
                        print
                        continue
                    print "Re-type the password for connection %s [%s]: " \
                        % (connection_name, connection.url)
                    password2 = getpass()
                    if password1 != password2:
                        print "Passwords do not match!"
                        print
                    else:
                        break
                connection.password = password1

        only_save =  new_connection_url \
            or options.set_step_stone \
            or options.change_tags \
            or options.set_password \
            or options.set_use_key

        if  only_save:
            library.save(connection)
            return None
        else:
            return connection

    def run(self):
        """ parse arguments and call the corresponding execution logic """
        stderr = sys.stderr
        self.parse_args()
        connection = self._process_args()
        options = self.options
        if not connection: # Connection was changed
            return
        sshclient = SSHClient(connection, self.host_library)
        if options.run_command or options.get_file or options.put_file  or options.run_su_script:
            sshclient.verbose = False
        try:
            sshclient.connect()
        except SSHException, err:
            stderr.write( "SSH error connecting to %s - %s\n"
                % (connection.name, err.args[0]))
            sys.exit(4)
        except socket.timeout:
            stderr.write("Connection timeout - unable  to connect to %s !\n"
                % connection.name)
            sys.exit(2)
        except socket.error, err:
            errorcode = err[0]
            if errorcode == errno.ECONNREFUSED:
                stderr.write("Connection refused - unable to connect to %s !\n"
                    % connection.name)
                sys.exit(3)
            else:
                raise
        if options.super:
            sshclient.perform_sudo()
        if options.run_su_script:
            sshclient.run_su_script(options.run_su_script)
        elif options.run_command:
            sshclient.run_command(options.run_command)
        elif options.get_file:
            sshclient.get_file(options.get_file)
        elif options.put_file:
            sshclient.put_file(options.put_file)
        else:
            sshclient.interactive_shell()
