#coding: utf-8

from _utilities import sort_uniq


class Summary(object):
    def __init__(self, invokeds=[], literals=[]):
        self.invokeds = tuple(sort_uniq(invokeds))
        self.literals = tuple(sort_uniq(literals))

    def __add__(self, other):
        return Summary(self.invokeds + other.invokeds,
                self.literals + other.literals)

    def __eq__(self, other):
        return isinstance(other, Summary) and \
            self.invokeds == other.invokeds and \
            self.literals == other.literals

    def __ne__(self, other):
        return not (isinstance(other, Summary) and \
            self.invokeds == other.invokeds and \
            self.literals == other.literals)

    def __repr__(self):
        return 'Summary(%s, %s)' % (repr(self.invokeds), repr(self.literals))

class SummaryBuilder(object):
    def __init__(self):
        self.invokeds = []
        self.literals = []

    def append_invoked(self, invoked):
        self.invokeds.append(invoked)

    def extend_invoked(self, invokeds):
        self.invokeds.extend(invokeds)

    def append_literal(self, literal):
        self.literals.append(literal)

    def extend_literal(self, literals):
        self.literals.extend(literals)

    def append_summary(self, sumry):
        self.invokeds.extend(sumry.invokeds)
        self.literals.extend(sumry.literals)

    def extend_summary(self, summaries):
        for sumry in summaries:
            self.invokeds.extend(sumry.invokeds)
            self.literals.extend(sumry.literals)

    def to_summary(self):
        return Summary(self.invokeds, self.literals)

