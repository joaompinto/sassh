# -*- coding: utf-8 -*-

DIGITS = '0123456789'
LOWERCASE = ''.join([chr(n) for n in range(ord('a'), ord('z')+1)])
UPPERCASE = ''.join([chr(n) for n in range(ord('A'), ord('Z')+1)])
LETTERS = "{0:s}{1:s}".format(LOWERCASE, UPPERCASE)
