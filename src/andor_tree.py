#coding: utf-8

from _utilities import sort_uniq

ORDERED_AND = "&"
ORDERED_OR = "|"

def normalize_tree(node):
    if not(isinstance(node, list) and node[0] in (ORDERED_AND, ORDERED_OR)):
        return node
    t0 = node[0]
    assert t0 in (ORDERED_AND, ORDERED_OR)
    t = [t0]
    for item in node[1:]:
        oi = normalize_tree(item)
        if oi == [ORDERED_OR]:
            if t0 == ORDERED_AND:
                t = oi[:]
                break  # for item
            else:
                continue  # for item
        if oi[0] == t0:
            t.extend(oi[1:])
        else:
            t.append(oi)
    if t0 == ORDERED_OR:
        st = [t0]
        st.extend(sort_uniq(t[1:]))
        t = st
    if len(t) == 2:
        return t[1]
    return t

def is_valid_tree(t):
    raise NameError("Not Yet Implemented")

