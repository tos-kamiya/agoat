#coding: utf-8

from andor_tree import ORDERED_AND, ORDERED_OR  # re-export


class CallNode(object):
    def __init__(self, invoked, recursive_cxt, body):
        self.invoked = invoked
        self.recursive_cxt = recursive_cxt
        self.body = body

    def __repr__(self):
        #return "CallNode(%s,%s,%s)" % (repr(self.invoked), repr(self.recursive_cxt), repr(self.body))
        return "CallNode(%s,%s,*)" % (repr(self.invoked), repr(self.recursive_cxt))

    # def __hash__(self):
    #     return hash(self.invoked) + hash(self.recursive_cxt) + hash(self.body)

    def __eq__(self, other):
        if not isinstance(other, CallNode):
            return False
        return self.invoked == other.invoked and \
                self.recursive_cxt == other.recursive_cxt and \
                self.body == other.body
