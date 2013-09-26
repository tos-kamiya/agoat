# coding: utf-8

import sys
import pprint

try:
    from sys import intern  # py3k
except:
    pass

from _utilities import sort_uniq

import summary
import calltree as ct
import calltree_builder as cb
import jimp_parser as jp
from _calltree_data_formatter import format_clzmsig


def _extract_callnode_labels_in_calltree(call_tree, label_set):
    def dig_node(node):
        if node is None:
            return
        elif isinstance(node, list):
            n0 = node[0]
            assert n0 in (ct.ORDERED_AND, ct.ORDERED_OR)
            for subn in node[1:]:
                dig_node(subn)
        elif isinstance(node, ct.CallNode):
            node_label = cb.callnode_label(node)
            if node_label in label_set:
                return
            label_set.add(node_label)
            if node.body:
                subnode = node.body
                if isinstance(subnode, (list, ct.CallNode)):
                    dig_node(subnode)
    dig_node(call_tree)


def extract_callnode_labels_in_calltrees(call_trees):
    label_set = set()
    for ct in call_trees:
        _extract_callnode_labels_in_calltree(ct, label_set)
    return sort_uniq(label_set)


def get_node_summary(node, summary_table, progress=None):
    """
    Get summary of a node.
    In case of summary_table parameter given, caluclate summary with memorization.
    Otherwise (without memorization), if two child nodes of a node is the same node,
    then calculate the summary twice (for each child node).
    """

    # summary_table = {}  # (ClzMethodSig, recursive_context) -> Summary

    def scan_invocation(node):
        assert isinstance(node, ct.Invoked)
        return intern(node.callee)

    def intern_literals(lits, lits_pool):
        for ls in lits_pool:
            if lits == ls:
                return ls
        else:
            return lits

    stack = []
    def dig_node(node):
        if node is None:
            return summary.Summary()
        elif isinstance(node, list):
            n0 = node[0]
            assert n0 in (ct.ORDERED_AND, ct.ORDERED_OR)
            len_node = len(node)
            if len_node == 1:
                return summary.Summary()
            elif len_node == 2:
                return dig_node(node[1])
            else:
                sb = summary.SummaryBuilder()
                for subn in node[1:]:
                    sb.append_summary(dig_node(subn))
                sumry = sb.to_summary()
                return sumry
        elif isinstance(node, ct.CallNode):
            invoked = node.invoked
            k = cb.callnode_label(node)
            stack.append(k)
            if summary_table is not None and k in summary_table:
                nodesum = summary_table[k]
            else:
                progress and progress(k)
                sb = summary.SummaryBuilder()
                subnode_literals = []
                subnode = node.body
                if subnode is None:
                    pass
                elif isinstance(subnode, (list, ct.CallNode)):
                    subnsum = dig_node(subnode)
                    sb.append_summary(subnsum)
                    subnode_literals.append(subnsum.literals)
                else:
                    sb.append_callee(scan_invocation(subnode))
                    lits = subnode.literals
                    if lits:
                        assert isinstance(lits, tuple)
                        sb.extend_literal(lits)
                        subnode_literals.append(lits)
                nodesum = sb.to_summary()
                nodesum.literals = intern_literals(nodesum.literals, subnode_literals)
                if summary_table is not None:
                    summary_table[k] = nodesum
            lits = invoked.literals
            parnetsum = nodesum + summary.Summary([invoked.callee], lits if lits else [])
            parnetsum.literals = intern_literals(parnetsum.literals, [nodesum.literals])
            stack.pop()
            return parnetsum
        else:
            return summary.Summary([scan_invocation(node)], node.literals)

    try:
        sumry = dig_node(node)
    except:
        sys.stderr.write("> warning: exception raised in get_node_summary:\n")
        pp = pprint.PrettyPrinter(indent=4, stream=sys.stderr)
        pp.pprint([format_clzmsig(clzmsig) for clzmsig, recursive_cxt in stack])
        sys.stderr.write('\n')
        raise

    assert not stack
    return sumry


def get_node_summary_wo_memoization(node):
    # summary_table = {}  # (ClzMethodSig, recursive_context) -> Summary
    summary_table = get_node_summary(node, summary_table=None)
    return summary_table


def extract_node_summary_table(nodes, progress=None):
    summary_table = {}  # (ClzMethodSig, recursive_context) -> Summary
    for node in nodes:
        get_node_summary(node, summary_table, progress=progress)
    return summary_table


def extract_entry_points(call_trees):
    entry_points = []
    for call_tree in call_trees:
        assert isinstance(call_tree, ct.CallNode)
        invoked = call_tree.invoked
        entry_points.append(invoked.callee)
    entry_points.sort()
    return entry_points


def main(argv, out=sys.stdout, logout=sys.stderr):
    dirname = argv[1]
    entry_point_class = argv[2]

    class_table = {}
    for clz, cd in jp.read_class_table_from_dir_iter(dirname):
        # sys.stderr.write("> %s\n" % clz)
        class_table[clz] = cd

    class_table = cb.inss_to_tree_in_class_table(class_table)

    entry_point = jp.ClzMethodSig(entry_point_class, None, "main", ("java.lang.String[]",))

    call_andor_tree = cb.extract_call_andor_trees(class_table, [entry_point])[0]
#     pp = pprint.PrettyPrinter(indent=4, stream=out)
#     pp.pprint(call_andor_tree)

    node_summary_table = extract_node_summary_table([call_andor_tree])
    pp = pprint.PrettyPrinter(indent=4, stream=out)
    pp.pprint(node_summary_table)


if __name__ == '__main__':
    main(sys.argv)
