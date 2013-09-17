# coding: utf-8

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


def sort_uniq(lst, key=None):
    if key:
        lst = sorted(lst, key=key)
    else:
        lst = sorted(lst)
    if len(lst) <= 1:
        return lst

    dummy = None if lst[0] is not None else 1
    return [item for item, prev_item in zip(lst, [dummy] + lst) if item != prev_item]


# @contextlib.contextmanager
# def auto_pop(lst):
#     original_length = len(lst)
#     yield
#     lst[:] = lst[:original_length]


@contextlib.contextmanager
def open_w_default(filename, mode, default):
    if filename == '-':
        yield default
    else:
        with open(filename, mode) as outp:
            yield outp


def list_flatten_iter(L):
    if isinstance(L, list):
        for li in L:
            for e in list_flatten_iter(li):
                yield e
    else:
        yield L

class progress_bar(object):
    def __init__(self, total_count, bar_length=60):
        assert total_count > 0
        assert bar_length > 0
        self.total_count = total_count
        self.bar_length = bar_length
        self.prev_per = None

    def __enter__(self):
        return self.report

    def report(self, count):
        per = count * 100.0 / self.total_count
        if not (count == self.total_count or self.prev_per is None or per >= self.prev_per + 0.1):
            return
        self.prev_per = per
        perb = int(count * self.bar_length / self.total_count)
        sys.stderr.write('\r%4.1f%% |%s%s|' % (per, '#' * perb, '-' * (self.bar_length - perb)))

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.prev_per is not None:
            sys.stderr.write('\n')
