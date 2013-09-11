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


class Uncontributing(object):
    def __init__(self, node):
        self.node = node

    def __str__(self):
        return "Uncontributing(len=%d)" % path_min_length(self.node)

    def __eq__(self, other):
        if not isinstance(other, Uncontributing):
            return False
        return self.node == other.node

    def __hash__(self):
        return hash(self.node)


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
            return Uncontributing(node) if r != True else node

        if r == False or not node:
            return Uncontributing(node)
        assert r is Undecided or r == True

        marked = []
        n0 = node[0]
        if n0 in (at.ORDERED_AND, at.ORDERED_OR):
            marked.append(n0)
            for subn in node[1:]:
                marked.append(mark_uncontributing_nodes_i(subn))
            if all(isinstance(subn, Uncontributing) for subn in marked[1:]):
                new_node = [n0]
                for subn in marked[1:]:
                    new_node.append(subn.node)
                return Uncontributing(new_node)
        else:
            assert False  # invalid tree
        return marked

    return mark_uncontributing_nodes_i(node)
