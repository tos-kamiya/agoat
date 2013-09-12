#coding: utf-8

import andor_tree as at

Undecided = object()

class HookResult(object):
    def __init__(self, value):
        self.value = value

def find_lower_bound_nodes(node, predicate_func):
    """
    Returns lower (that is, further from the root) bound nodes that satisfy the predciate.
    The predicate_func returns either True (satisfy), False (not satisfy), Undecided (unknown. may or maynot).
    The predicate_func has to hold the following properties: 
    (1) If a node is decided to not satisfy the predicate, none of its descendant nodes satisfies.
    (2) If none of descendant nodes of a node is decided to satisfy the predicate, the node is decided to not satisfy.
    Besides, if special treatment is needed to some node, the predicate_func can return a HookResult object.
    When a HookResult object is returned, its value is used as a result for the node.
    """

    def find_lower_bound_nodes_i(node):
        r = predicate_func(node)
        if isinstance(r, HookResult):
            return r.value
        if not isinstance(node, list):
            return [node] if r == True else []

        if r == False:
            return []
        assert r is Undecided or r == True

        lower_bound_nodes = []
        if node:
            n0 = node[0]
            if n0 in (at.ORDERED_AND, at.ORDERED_OR):
                for subn in node[1:]:
                    subns = find_lower_bound_nodes_i(subn)
                    if subns:
                        lower_bound_nodes.extend(subns)
            else:
                assert False  # invalid tree
        if lower_bound_nodes:
            return lower_bound_nodes

        return [node] if r == True else []

    return find_lower_bound_nodes_i(node)


def path_min_length(node, weighting_func=None):
    def path_min_length_i(node):
        if weighting_func is not None:
            L = weighting_func(node)
            if L is not None:
                return L
        if not isinstance(node, list):
            return 1
        if not node:
            return 0
        n0 = node[0]
        if n0 == at.ORDERED_AND:
            return sum(path_min_length_i(subn) for subn in node[1:])
        elif n0 == at.ORDERED_OR:
            return min(path_min_length_i(subn) for subn in node[1:])
        else:
            assert False  # invalid tree
    return path_min_length_i(node)


