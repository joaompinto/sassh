#!/usr/bin/env python
# -*- coding: utf-8 -*-


from time import time
from itertools import chain
from random import seed, choice, sample
from sassh.string import UPPERCASE, LETTERS, LOWERCASE, DIGITS

def mkpasswd(length=8, digits=2, upper=2, lower=2, symbols=2):
    """  Create a random password  """

    seed(time())

    symbol_chars = '.!@$%^&*()'
    other_chars_len = length - digits - upper - lower - symbols

    password = list(
        chain(
            (choice(UPPERCASE) for _ in range(upper)),
            (choice(LOWERCASE) for _ in range(lower)),
            (choice(DIGITS) for _ in range(digits)),
            (choice(symbol_chars) for _ in range(symbols)),
            (choice(LETTERS) for _ in range(other_chars_len))
        )
    )

    return "".join(sample(password, len(password)))
