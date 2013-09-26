#coding: utf-8

from _utilities import sort_uniq


class Summary(object):
    __slots__ = ('callees', 'literals')

    def __getstate__(self):
        return self.callees, self.literals

    def __setstate__(self, tpl):
        self.callees, self.literals = tpl

    def __init__(self, callees=(), literals=()):
        self.callees = sort_uniq(callees)
        self.literals = sort_uniq(literals)

    def __eq__(self, other):
        return isinstance(other, Summary) and \
            self.callees == other.callees and \
            self.literals == other.literals

    def __ne__(self, other):
        return not (isinstance(other, Summary) and \
            self.callees == other.callees and \
            self.literals == other.literals)

    def __repr__(self):
        return 'Summary(%s, %s)' % (repr(self.callees), repr(self.literals))

class SummaryBuilder(object):
    def __init__(self):
        self.callees = []
        self.literals = []

    def append_callee(self, callee):
        self.callees.append(callee)

    def extend_callee(self, callees):
        self.callees.extend(callees)

    def append_literal(self, literal):
        self.literals.append(literal)

    def extend_literal(self, literals):
        self.literals.extend(literals)

    def append_summary(self, sumry):
        self.callees.extend(sumry.callees)
        self.literals.extend(sumry.literals)

    def extend_summary(self, summaries):
        for sumry in summaries:
            self.callees.extend(sumry.callees)
            self.literals.extend(sumry.literals)

    def to_summary(self):
        return Summary(self.callees, self.literals)

