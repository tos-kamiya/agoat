# coding: utf-8

import sys
import pprint

try:
    from sys import intern  # py3k
except:
    pass

from _utilities import sort_uniq

import sammary
import calltree as ct
import calltree_builder as cb
import jimp_parser as jp
from _calltree_data_formatter import format_clz_msig


def _extract_callnode_invokeds_in_calltree(call_tree, invoked_set):
    def dig_node(node):
        if node is None:
            return
        elif isinstance(node, list):
            n0 = node[0]
            assert n0 in (ct.ORDERED_AND, ct.ORDERED_OR)
            for subn in node[1:]:
                dig_node(subn)
        elif isinstance(node, ct.CallNode):
            invoked = node.invoked
            assert invoked[0] in (jp.INVOKE, jp.SPECIALINVOKE)
            clz, msig = invoked[1], invoked[2]
            k = (clz, msig, node.recursive_cxt)
            if k in invoked_set:
                return
            invoked_set.add(k)
            if node.body:
                subnode = node.body
                if isinstance(subnode, (list, ct.CallNode)):
                    dig_node(subnode)
    dig_node(call_tree)


def extract_callnode_invokeds_in_calltrees(call_trees):
    invoked_set = set()
    for ct in call_trees:
        _extract_callnode_invokeds_in_calltree(ct, invoked_set)
    return sort_uniq(invoked_set)


def get_node_sammary(node, sammary_table, progress=None):
    """
    Get sammary of a node.
    In case of sammary_table parameter given, caluclate sammary with memorization.
    Otherwise (without memorization), if two child nodes of a node is the same node,
    then calculate the sammary twice (for each child node).
    """

    # sammary_table = {}  # (clz, MethodSig, recursive_context) -> Sammary

    def scan_invocation(node):
        assert isinstance(node, tuple)
        assert node[0] in (jp.INVOKE, jp.SPECIALINVOKE)
        invoked = '%s\t%s' % (node[1], node[2])
        return intern(invoked)

    def intern_literals(lits, lits_pool):
        for ls in lits_pool:
            if lits == ls:
                return ls
        else:
            return lits

    stack = []
    def dig_node(node):
        if node is None:
            return sammary.Sammary()
        elif isinstance(node, list):
            n0 = node[0]
            assert n0 in (ct.ORDERED_AND, ct.ORDERED_OR)
            len_node = len(node)
            if len_node == 1:
                return sammary.Sammary()
            elif len_node == 2:
                return dig_node(node[1])
            else:
                sb = sammary.SammaryBuilder()
                for subn in node[1:]:
                    sb.append_sammary(dig_node(subn))
                sam = sb.to_sammary()
                return sam
        elif isinstance(node, ct.CallNode):
            invoked = node.invoked
            assert invoked[0] in (jp.INVOKE, jp.SPECIALINVOKE)
            clz, msig = invoked[1], invoked[2]
            k = (clz, msig, node.recursive_cxt)
            stack.append(k)
            if sammary_table is not None and k in sammary_table:
                nodesam = sammary_table[k]
            else:
                progress and progress(k)
                sb = sammary.SammaryBuilder()
                subnode_literals = []
                subnode = node.body
                if subnode is None:
                    pass
                elif isinstance(subnode, (list, ct.CallNode)):
                    subnsam = dig_node(subnode)
                    sb.append_sammary(subnsam)
                    subnode_literals.append(subnsam.literals)
                else:
                    sb.append_invoked(scan_invocation(subnode))
                    lits = subnode[3]
                    if lits:
                        assert isinstance(lits, tuple)
                        sb.extend_literal(lits)
                        subnode_literals.append(lits)
                nodesam = sb.to_sammary()
                nodesam.literals = intern_literals(nodesam.literals, subnode_literals)
                if sammary_table is not None:
                    sammary_table[k] = nodesam
            lits = invoked[3]
            parentsam = nodesam + sammary.Sammary(['%s\t%s' % (clz, msig)], lits if lits else [])
            parentsam.literals = intern_literals(parentsam.literals, [nodesam.literals])
            stack.pop()
            return parentsam
        else:
            return sammary.Sammary([scan_invocation(node)], node[3])

    try:
        sam = dig_node(node)
    except:
        sys.stderr.write("> warning: exception raised in get_node_sammary:\n")
        pp = pprint.PrettyPrinter(indent=4, stream=sys.stderr)
        pp.pprint([format_clz_msig(clz, msig) for clz, msig, recursive_cxt in stack])
        sys.stderr.write('\n')
        raise

    assert not stack
    return sam


def get_node_sammary_wo_memoization(node):
    return get_node_sammary(node, sammary_table=None)


def extract_node_sammary_table(nodes, progress=None):
    sammary_table = {}
    for node in nodes:
        get_node_sammary(node, sammary_table, progress=progress)
    return sammary_table


def main(argv, out=sys.stdout, logout=sys.stderr):
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

    node_sammary_table = extract_node_sammary_table([call_andor_tree])
    pp = pprint.PrettyPrinter(indent=4, stream=out)
    pp.pprint(node_sammary_table)


if __name__ == '__main__':
    main(sys.argv)
