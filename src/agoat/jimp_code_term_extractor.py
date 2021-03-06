# coding: utf-8

import sys

from collections import namedtuple

from ._utilities import sort_uniq

from . import jimp_parser as jp
from . import _jimp_code_body_to_tree_elem as jcbte


Summary = namedtuple("Summary", "callees, literals")


class SummaryBuilder(object):
    def __init__(self):
        self.callees = []
        self.literals = []

    def extend_callee(self, callees):
        self.callees.extend(callees)

    def extend_literal(self, literals):
        self.literals.extend(literals)

    def append_summary(self, sumry):
        self.callees.extend(sumry.callees)
        self.literals.extend(sumry.literals)

    def to_summary(self):
        return Summary(self.callees, self.literals)


def extract_referred_literals(inss, method_data, class_data):
    if inss is None:
        return Summary((), ())

    resolve_type = jcbte.gen_type_resolver(method_data, class_data)

    sb = SummaryBuilder()
    for ins in inss:
        cmd = ins[0]
        if cmd in (jp.SPECIALINVOKE, jp.INVOKE):
            receiver, method_name, args, retv, linenum = ins[1:]
            lits = [resolve_type(receiver)[1]]
            lits.extend(resolve_type(a)[1] for a in args)
            lits.append(resolve_type(retv)[1])
            lits = filter(lambda L: L is not None, lits)
            sb.extend_literal(lits)

    return sb.to_summary()


def extract_defined_methods(class_data):
    sb = SummaryBuilder()
    sb.extend_callee(class_data.methods.iterkeys())
    return sb.to_summary()


def extract_defined_methods_table(class_table):
    sb = SummaryBuilder()
    for clz, cd in class_table.iteritems():
        sb.append_summary(extract_defined_methods(cd))
    return sb.to_summary()


def main(argv, out=sys.stdout):
    dirname = argv[1]
    class_table = {}
    for clz, cd in jp.read_class_table_from_dir_iter(dirname):
        class_table[clz] = cd
    sumry = extract_defined_methods_table(class_table)
    for clz, msig in sumry.callees:
        out.write("%s\t%s\n" % (clz, msig))


if __name__ == '__main__':
    main(sys.argv)
