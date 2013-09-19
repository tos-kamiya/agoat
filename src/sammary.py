#coding: utf-8

from _utilities import sort_uniq


class Sammary(object):
    def __init__(self, invokeds=[], literals=[]):
        self.invokeds = tuple(sort_uniq(invokeds))
        self.literals = tuple(sort_uniq(literals))

    def __add__(self, other):
        return Sammary(self.invokeds + other.invokeds,
                self.literals + other.literals)

    def __eq__(self, other):
        return isinstance(other, Sammary) and \
            self.invokeds == other.invokeds and \
            self.literals == other.literals

    def __ne__(self, other):
        return not (isinstance(other, Sammary) and \
            self.invokeds == other.invokeds and \
            self.literals == other.literals)

    ## debug
    # def __repr__(self):
    #     return 'Summary(%s,%s)' % (repr(self.invokeds), repr(self.literals))

class SammaryBuilder(object):
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

    def append_sammary(self, sammary):
        self.invokeds.extend(sammary.invokeds)
        self.literals.extend(sammary.literals)

    def extend_sammary(self, sammaries):
        for sammary in sammaries:
            self.invokeds.extend(sammary.invokeds)
            self.literals.extend(sammary.literals)

    def to_sammary(self):
        return Sammary(self.invokeds, self.literals)

