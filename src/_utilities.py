#coding: utf-8

__author__ = 'Toshihiro Kamiya <kamiya@mbj.nifty.com>'
__status__ = 'experimental'

import contextlib
import sys
import urllib2

ASCII_SYMBOLS_EXCEPT_FOR_PERCENT = " \t!\"#$&`()*+,-./:;<=>?@[\\]^_'{|}~"

def readline_iter(filename):
    if filename != '-':
        with open(filename, "rb") as f:
            for L in f:
                L = L.decode('utf-8').rstrip().encode('utf-8')
                L = urllib2.quote(L, safe=ASCII_SYMBOLS_EXCEPT_FOR_PERCENT)
                yield L
    else:
        for L in sys.stdin:
            L = L.decode('utf-8').rstrip().encode('utf-8')
            L = urllib2.quote(L, safe=ASCII_SYMBOLS_EXCEPT_FOR_PERCENT)
            yield L

def sort_uniq(lst):
    lst.sort()
    if len(lst) <= 1:
        return lst

    dummy = None if lst[0] is not None else 1
    return [item for item, prev_item in zip(lst, [dummy] + lst) if item != prev_item]

@contextlib.contextmanager
def auto_pop(lst):
    original_length = len(lst)
    yield
    lst[:] = lst[:original_length]
