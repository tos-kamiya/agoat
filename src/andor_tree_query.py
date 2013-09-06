#coding: utf-8

from andor_tree import ORDERED_AND, ORDERED_OR

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
            if n0 in (ORDERED_AND, ORDERED_OR):
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


UNCONTRIBUTING = 'uncontributing'


def mark_uncontributing_nodes(node, predicate_func):
    """
    The predicate_func returns either True (contributing), False (not contributing), Undecided (unknown. may or maynot).
    The predicate_func has to hold the following property:
    (1) If a node is decided to not contribute, none of its descendant nodes contributes.
    (2) If none of descendant nodes of a node is decided to contribute, the node is decided to not contribute.
    Besides, if special treatment is needed to some node, the predicate_func can return a HookResult object.
    When a HookResult object is returned, its value is used as a result for the node.
    """

    def mark_uncontributing_nodes_i(node):
        r = predicate_func(node)
        if isinstance(r, HookResult):
            return r.value
        if not isinstance(node, list):
            return [UNCONTRIBUTING, node] if r != True else node

        if r == False:
            return [UNCONTRIBUTING, node]
        assert r is Undecided or r == True

        marked = []
        n0 = node[0]
        if n0 in (ORDERED_AND, ORDERED_OR):
            marked.append(n0)
            for subn in node[1:]:
                marked.append(mark_uncontributing_nodes_i(subn))
            if all((isinstance(subn, list) and subn and subn[0] == UNCONTRIBUTING) for subn in marked[1:]):
                return [UNCONTRIBUTING, node]
        else:
            assert False  # invalid tree
        return marked

    return mark_uncontributing_nodes_i(node)
