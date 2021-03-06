# coding: utf-8

from ._utilities import sort_uniq


ORDERED_AND = "&&"
ORDERED_OR = "||"


def normalize_tree(node):
    if not(isinstance(node, list) and node and node[0] in (ORDERED_AND, ORDERED_OR)):
        return node
    t0 = node[0]
    assert t0 in (ORDERED_AND, ORDERED_OR)
    if t0 == ORDERED_OR:
        items = []
        nodes = []
        for item in node[1:]:
            oi = normalize_tree(item)
            if oi == [ORDERED_OR]:
                continue  # for item
            if isinstance(oi, list) and oi:
                oi0 = oi[0]
                if oi0 == ORDERED_OR:
                    nodes.extend(oi[1:])
                elif oi0 == ORDERED_AND:
                    nodes.append(oi)
                else:
                    items.append(oi)
            else:
                items.append(oi)
        t = [t0]
        t.extend(sort_uniq(items))
        t.extend(sort_uniq(nodes))
    else:
        t = [t0]
        for item in node[1:]:
            oi = normalize_tree(item)
            if oi == [ORDERED_OR]:
                return oi[:]
            if isinstance(oi, list) and oi and oi[0] == ORDERED_AND:
                t.extend(oi[1:])
            else:
                t.append(oi)
    if len(t) == 2:
        return t[1]
    return t

