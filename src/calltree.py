#coding: utf-8

from andor_tree import ORDERED_AND, ORDERED_OR  # re-export


#Invoked = collections.namedtuple('Invoked', 'cmd callee literals locinfo')
class Invoked(object):
    def __init__(self, cmd, callee, literals, locinfo):
        self.cmd = cmd
        self.callee = callee
        self.literals = literals
        self.locinfo = locinfo

    def __repr__(self):
        return "Invoked(%s, %s, %s, %s)" % (repr(self.cmd), repr(self.callee), repr(self.literals), repr(self.locinfo))

    def __eq__(self, other):
        if not isinstance(other, Invoked):
            return False
        return self.cmd == other.cmd and \
            self.callee == other.callee and \
            self.literals == other.literals and \
            self.locinfo == other.locinfo

    def __ne__(self, other):
        if not isinstance(other, Invoked):
            return True
        return self.cmd != other.cmd or \
            self.callee != other.callee or \
            self.literals != other.literals or \
            self.locinfo != other.locinfo


class CallNode(object):
    def __init__(self, invoked, recursive_cxt, body):
        self.invoked = invoked
        self.recursive_cxt = recursive_cxt
        self.body = body

    def __repr__(self):
        return "CallNode(%s, %s, *)" % (repr(self.invoked), repr(self.recursive_cxt))

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
