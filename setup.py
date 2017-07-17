#!/usr/bin/env python
# -*- coding: utf-8 -*-


from distutils.core import setup

setup(name='sassh',
      version='0.4.3',
      install_requirements= ['pygpgme', 'paramiko'],
      description='SysAdmin SSH connection manager/client',
      author='João Pinto',
      author_email='<joao.pinto@pt.ibm.com>',
      packages=['sassh'],
      scripts=['bin/sassh'],
      )
