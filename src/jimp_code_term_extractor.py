# coding: utf-8

import sys

from _utilities import sort_uniq

import jimp_parser as jp
import _jimp_code_body_to_tree_elem as jcbte

def extract_invoked_methods(inss, method_data, class_data):
    resolve = jcbte.gen_resolver(method_data, class_data)

    invoked_recv_msigs = []
    for ins in inss:
        cmd = ins[0]
        if cmd in (jp.SPECIALINVOKE, jp.INVOKE):
            receiver, method_name, args, retv, linenum = ins[1:]
            rreceiver = resolve(receiver) or receiver
            rargs = tuple(map(resolve, args))
            rretv = resolve(retv)
            msig = jcbte.method_sig_intern(jp.MethodSig(rretv, method_name, rargs))
            invoked_recv_msigs.append((rreceiver, msig))

    return sort_uniq(invoked_recv_msigs)


def extract_defined_methods(class_data):
    clz = class_data.class_name

    defined_clz_msigs = []
    for msig, md in sorted(class_data.methods.iteritems()):
        defined_clz_msigs.append((clz, msig))

    return defined_clz_msigs


def extract_methods(class_table):
    method_set = set()
    for clz, cd in class_table.iteritems():
        method_set.update(extract_defined_methods(cd))
        for msig, md in cd.methods.iteritems():
            method_set.update(extract_invoked_methods(md.code, md, cd))

    return sorted(method_set)


def main(argv, out=sys.stdout):
    dirname = argv[1]
    class_table = {}
    for clz, cd in jp.read_class_table_from_dir_iter(dirname):
        class_table[clz] = cd
    methods = extract_methods(class_table)
    for clz, msig in methods:
        out.write("%s\t%s\n" % (clz, msig))


if __name__ == '__main__':
    main(sys.argv)
