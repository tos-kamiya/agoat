# coding: utf-8

import sys

from andor_tree import ORDERED_AND, ORDERED_OR
from calltree_builder import CallNode, NOTREE
from jimp_parser import INVOKE, SPECIALINVOKE

import jimp_parser as jp
import calltree_builder as cb


def summarize_node(node):
    def scan_invocation(node):
        if not isinstance(node, tuple):
            assert False  # debug
        assert isinstance(node, tuple)
        assert node[0] in (INVOKE, SPECIALINVOKE)
        clz = node[1]
        msig = node[2]
        return (clz, msig)

    summary = set()
    def dig_node(node):
        if isinstance(node, list):
            n0 = node[0]
            if n0 in (ORDERED_AND, ORDERED_OR):
                for subn in node[1:]:
                    dig_node(subn)
            elif n0 == NOTREE:
                raise ValueError("NOTREE not yet supported")
            else:
                assert False
        elif isinstance(node, CallNode):
            invoked = node.invoked
            assert invoked[0] in (INVOKE, SPECIALINVOKE)
            clz_msig = invoked[1], invoked[2]
            summary.add(clz_msig)
            subnode = node.body
            if subnode == NOTREE:
                raise ValueError("NOTREE not yet supported")
            if subnode is None:
                pass
            elif isinstance(subnode, (list, CallNode)):
                dig_node(subnode)
        else:
            summary.add(scan_invocation(node))

    dig_node(node)
    return summary


def extract_node_summary_table(call_andor_tree, summary_memo={}):
    # summary_memo = {}  # (clz, MethodSig, recursive_context) -> list of (clz, MethodSig)
    def scan_invocation(node):
        assert isinstance(node, tuple)
        assert node[0] in (INVOKE, SPECIALINVOKE)
        clz = node[1]
        msig = node[2]
        return [(clz, msig)]
    def dig_node(node):
        if isinstance(node, list):
            n0 = node[0]
            if n0 in (ORDERED_AND, ORDERED_OR):
                subsum = set()
                for subn in node[1:]:
                    subsum.update(dig_node(subn))
                return sorted(subsum)
            elif n0 == NOTREE:
                raise ValueError("NOTREE not yet supported")
            else:
                assert False
        elif isinstance(node, CallNode):
            invoked = node.invoked
            assert invoked[0] in (INVOKE, SPECIALINVOKE)
            clz_msig = clz, msig = invoked[1], invoked[2]
            subsum = set([clz_msig])
            k = (clz, msig, node.recursive_cxt)
            if k not in summary_memo:
                subnode = node.body
                if subnode == NOTREE:
                    raise ValueError("NOTREE not yet supported")
                if subnode is None:
                    pass
                elif isinstance(subnode, (list, CallNode)):
                    subsum.update(dig_node(subnode))
                else:
                    subsum.update(scan_invocation(subnode))
                sorted_subsum = summary_memo[k] = sorted(subsum)
            else:
                sorted_subsum = summary_memo[k]
            return sorted_subsum
        else:
            return scan_invocation(node)

    dig_node(call_andor_tree)
    return summary_memo


def main(argv, out=sys.stdout, logout=sys.stderr):
    import pprint

    dirname = argv[1]
    entry_point_class = argv[2]

    class_table = {}
    for clz, cd in jp.read_class_table_from_dir_iter(dirname):
        # sys.stderr.write("> %s\n" % clz)
        class_table[clz] = cd

    class_table = cb.inss_to_tree_in_class_table(class_table)

    entry_point_msig = jp.MethodSig(None, "main", ("java.lang.String[]",))
    entry_point = (entry_point_class, entry_point_msig)

    call_andor_tree = cb.extract_call_andor_trees(class_table, [entry_point])[0]
#     pp = pprint.PrettyPrinter(indent=4, stream=out)
#     pp.pprint(call_andor_tree)

    node_summary_table = extract_node_summary_table(call_andor_tree)
    pp = pprint.PrettyPrinter(indent=4, stream=out)
    pp.pprint(node_summary_table)

if __name__ == '__main__':
    main(sys.argv)
