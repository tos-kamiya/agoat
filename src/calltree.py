#coding: utf-8

import functools

from andor_tree import ORDERED_AND, ORDERED_OR  # re-export


@functools.total_ordering
class Node(object):
    def __init__(self, label):
        self.label = label

    def __repr__(self):
        return "Node(%s)" % repr(self.label)

    def __hash__(self):
        return hash(self.label)

    def __eq__(self, other):
        if not isinstance(other, Node):
            return False
        return self.label == other.label

    def __lt__(self, other):
        if not isinstance(other, Node):
            assert False
        return self.label < other.label


class CallNode(object):
    def __init__(self, invoked, recursive_cxt, body):
        self.invoked = invoked
        self.recursive_cxt = recursive_cxt
        self.body = body

    def __repr__(self):
        # return "CallNode(%s,%s,%s)" % (repr(self.invoked), repr(self.recursive_cxt), repr(self.body))  #debug
        if isinstance(self.body, Node):
            return "CallNode(%s,%s,%s)" % (repr(self.invoked), repr(self.recursive_cxt), repr(self.body))
        if isinstance(self.invoked, tuple):
            invoked_repr = repr(tuple(self.invoked[:3]))
        else:
            invoked_repr = repr(self.invoked),
        return "CallNode(%s,*,*)" % (invoked_repr)

    # def __hash__(self):
    #     return hash(self.invoked) + hash(self.recursive_cxt) + hash(self.body)

    def __eq__(self, other):
        if not isinstance(other, CallNode):
            return False
        return self.invoked == other.invoked and \
                self.recursive_cxt == other.recursive_cxt and \
                self.body == other.body

    def __ne__(self, other):
        if not isinstance(other, CallNode):
            return True
        return self.invoked != other.invoked or \
                self.recursive_cxt != other.recursive_cxt or \
                self.body != other.body
