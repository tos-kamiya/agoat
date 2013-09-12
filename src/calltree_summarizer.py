# coding: utf-8

import sys

from _utilities import sort_uniq

import calltree as ct
import calltree_builder as cb
import jimp_parser as jp


def get_node_summary(node, summary_table):
    """
    Get summary of a node.
    In case of summary_table parameter given, caluclate summary with memorization.
    Otherwise (without memorization), if two child nodes of a node is the same node,
    then calculate the summary twice (for each child node).
    """

    # summary_table = {}  # (clz, MethodSig, recursive_context) -> list of (clz, MethodSig)
    def scan_invocation(node):
        assert isinstance(node, tuple)
        assert node[0] in (jp.INVOKE, jp.SPECIALINVOKE)
        return (node[1], node[2])

    def dig_node(node):
        if node is None:
            return []
        elif isinstance(node, list):
            n0 = node[0]
            if n0 in (ct.ORDERED_AND, ct.ORDERED_OR):
                nodesum = set()
                for subn in node[1:]:
                    nodesum.update(dig_node(subn))
                return sorted(nodesum)
            else:
                assert False
        elif isinstance(node, ct.CallNode):
            invoked = node.invoked
            assert invoked[0] in (jp.INVOKE, jp.SPECIALINVOKE)
            clz_msig = clz, msig = invoked[1], invoked[2]
            k = (clz, msig, node.recursive_cxt)
            if summary_table is not None and k in summary_table:
                nodesum = set(summary_table[k])
            else:
                nodesum = set()
                subnode = node.body
                if subnode is None:
                    pass
                elif isinstance(subnode, (list, ct.CallNode)):
                    nodesum.update(dig_node(subnode))
                else:
                    nodesum.add(scan_invocation(subnode))
                    subnode[3] and nodesum.update(subnode[3])
                if summary_table is not None:
                    summary_table[k] = sorted(nodesum)
            parnetsum = nodesum
            parnetsum.add(clz_msig)
            invoked[3] and parnetsum.update(invoked[3])
            return parnetsum
        else:
            s = [scan_invocation(node)]
            node[3] and s.extend(node[3])
            return sort_uniq(s)

    return dig_node(node)


def get_node_summary_wo_memoization(node):
    return get_node_summary(node, summary_table=None)


def extract_node_summary_table(nodes):
    summary_table = {}
    for node in nodes:
        get_node_summary(node, summary_table)
    return summary_table


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

    node_summary_table = extract_node_summary_table([call_andor_tree])
    pp = pprint.PrettyPrinter(indent=4, stream=out)
    pp.pprint(node_summary_table)


if __name__ == '__main__':
    main(sys.argv)
