#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import gpgme
from glob import glob
from os import makedirs
from os.path import join, exists, basename
from xdg.BaseDirectory import xdg_config_home
from StringIO import StringIO
from lxml.builder import ElementMaker
import lxml.etree as etree

class Connection:
    """ Container for a connection information """

    def __init__(self, name):
        self.name = name
        self.url = None
        self.step_stone = None
        self.password = None
        self.tags = None
        self.use_key = False

    def change_tags(self, tags):
        """ Change tags for the current connection """
        self.tags = tags

class Library:
    """ Retrieve/update information from the connections library """
    def __init__(self, namespace, keyid):
        self.basedir = join(xdg_config_home, namespace, 'connections')
        self.ctx = gpgme.Context()
        self.key = self.ctx.get_key(keyid)

    def getbyname(self, name):
        """ Return connection with the specified name """
        conn_info_filename = join(self.basedir, name+'.gpg')
        with open(conn_info_filename) as conn_file:
            encrypted = StringIO(conn_file.read())
        plain = StringIO()
        self.ctx.decrypt(encrypted, plain)
        record = etree.fromstring(plain.getvalue())
        iterator = record.getiterator()
        conn = Connection(None)
        for i in iterator:
            value = i.text
            if i.tag == 'use_key':
                value = True if value =='True' else False
            setattr(conn, i.tag, value)
        return conn

    def save(self, connection):
        """ Save connection in the connection library """
        if not exists(self.basedir):
            makedirs(self.basedir)
        conn_info_filename = join(self.basedir, connection.name+'.gpg_new')
        final_info_filename = join(self.basedir, connection.name+'.gpg')
        # Encrypt the object string before saving
        cipher = StringIO()

        record = etree.Element("record")

        for attr in connection.__dict__:
            value = connection.__dict__[attr]
            if attr == 'use_key':
                value = 'True' if value else 'False'
            if attr == "record": # Fix void record element inserted from bug
                continue
            if isinstance(value, (str, unicode)):
                if not value: # Don't add empty elements
                    continue
                element =  etree.Element(attr)
                element.text = value
                record.append(element)
        xml = etree.tostring(record, pretty_print=True)

        self.ctx.encrypt([self.key ], 0, StringIO(xml), cipher)
        with open(conn_info_filename, 'w') as conn_file:
            conn_file.write(cipher.getvalue())
        os.rename(conn_info_filename, final_info_filename)


    def remove(self, connection):
        """ Remove connection from the connections library """
        conn_info_filename = join(self.basedir, connection.name)
        os.unlink(conn_info_filename+'.gpg')

    @property
    def connections(self):
        """ Return the list of names for the connections """
        conn_files = glob(join(self.basedir, '*.gpg'))
        conn_list = [basename(x).replace('.gpg', '') for x in conn_files]
        return sorted(conn_list)
