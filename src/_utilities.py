# coding: utf-8

import contextlib
import sys
import re


def quote(unicode_str):
    pat_unicode_escape = re.compile(r"[\\](u[0-9a-fA-F]{4}|U[0-9a-fA-F]{8})")
    buf = []
    last_pos = 0
    for m in pat_unicode_escape.finditer(unicode_str):
        s, e = m.span()
        buf.append(unicode_str[last_pos:s].encode("unicode-escape"))
        buf.append(unicode_str[s:e].encode('utf-8'))
        last_pos = e
    else:
        buf.append(unicode_str[last_pos:].encode("unicode-escape"))
    return ''.join(buf)


def readline_iter(filename):
    with open(filename, "rb") as f:
        for L in f:
            yield quote(L.decode("utf-8").rstrip())


def sort_uniq(lst, key=None):
    if key:
        lst = sorted(lst, key=key)
    else:
        lst = sorted(lst)
    if len(lst) <= 1:
        return lst

    t = [lst[0]]
    for item in lst:
        if item != t[-1]:
            t.append(item)
    return t


def list_flatten_iter(L):
    if isinstance(L, list):
        for li in L:
            for e in list_flatten_iter(li):
                yield e
    else:
        yield L


if sys.platform == "win32":
    STDOUT = STDIN = "CON"
else:
    STDOUT = "/dev/stdout"
    STDIN = "/dev/stdin"
