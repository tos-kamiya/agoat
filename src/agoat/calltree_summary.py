# coding: utf-8

import sys
import pprint

try:
    from sys import intern  # py3k
except:
    pass

from ._utilities import sort_uniq

from . import calltree as ct
from . import calltree_builder as cb
from . import jimp_parser as jp


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
        self.already_appended_callnodes = set()

    def append_callee(self, callee):
        self.callees.append(callee)

    def extend_callee(self, callees):
        self.callees.extend(callees)

    def append_literal(self, literal):
        self.literals.append(literal)

    def extend_literal(self, literals):
        self.literals.extend(literals)

    def append_summary(self, sumry, callnode_label=None):
        self.callees.extend(sumry.callees)
        self.literals.extend(sumry.literals)
        if callnode_label is not None:
            self.already_appended_callnodes.add(callnode_label)

    def to_summary(self):
        return Summary(self.callees, self.literals)


# def _extract_callnode_labels_in_calltree(call_tree, label_set):
#     def dig_node(node):
#         if node is None:
#             return
#         elif isinstance(node, list):
#             n0 = node[0]
#             assert n0 in (ct.ORDERED_AND, ct.ORDERED_OR)
#             for subn in node[1:]:
#                 dig_node(subn)
#         elif isinstance(node, ct.CallNode):
#             node_label = cb.callnode_label(node)
#             if node_label in label_set:
#                 return
#             label_set.add(node_label)
#             if node.body:
#                 subnode = node.body
#                 if isinstance(subnode, (list, ct.CallNode)):
#                     dig_node(subnode)
#         else:
#             assert False
#     dig_node(call_tree)
# 
# 
# def extract_callnode_labels_in_calltrees(call_trees):
#     label_set = set()
#     for ct in call_trees:
#         _extract_callnode_labels_in_calltree(ct, label_set)
#     return sort_uniq(label_set)


def get_node_summary(node, summary_table, use_callnode_label_with_depth=False):
    """
    Get summary of a node.
    In case of summary_table parameter given, calculate summary with memorization.
    Otherwise (without memorization), if two child nodes of a node is the same node,
    then calculate the summary twice (for each child node).
    """

    # summary_table = {}  # (ClzMethodSig, recursive_context) -> Summary

    def intern_literals(lits, lits_pool):
        for plits in lits_pool:
            if plits == lits:
                return plits
        else:
            return lits

    stack = []

    if use_callnode_label_with_depth:
        def cl(call_node):
            return (call_node.invoked.callee, len(stack))
        callnode_label = cl
    else:
        callnode_label = cb.callnode_label

    def dig_node(node, parent_summary_builder, child_literals_holder):
        if node is None:
            return
        elif isinstance(node, list):
            n0 = node[0]
            assert n0 in (ct.ORDERED_AND, ct.ORDERED_OR)
            for subn in node[1:]:
                dig_node(subn, parent_summary_builder, child_literals_holder)
            return
        elif isinstance(node, ct.CallNode):
            invoked = node.invoked
            lits = invoked.literals
            lits and parent_summary_builder.extend_literal(lits)
            lbl = callnode_label(node)
            if lbl not in parent_summary_builder.already_appended_callnodes:
                stack.append(lbl)
                nodesum = summary_table.get(lbl)
                if nodesum is None:
                    sb = SummaryBuilder()
                    clh = []
                    subnode = node.body
                    if subnode is None:
                        pass
                    elif isinstance(subnode, (list, ct.CallNode)):
                        dig_node(subnode, sb, clh)
                    elif isinstance(subnode, ct.Invoked):
                        sb.append_callee(intern(subnode.callee))
                        lits = subnode.literals
                        if lits:
                            sb.extend_literal(lits)
                            clh.append(lits)
                    else:
                        assert False
                    nodesum = sb.to_summary()
                    nodesum.literals = intern_literals(nodesum.literals, clh)
                    summary_table[lbl] = nodesum
                parent_summary_builder.append_summary(nodesum, lbl)
                parent_summary_builder.append_callee(invoked.callee)
                child_literals_holder.append(nodesum.literals)
                stack.pop()
            return
        elif isinstance(node, ct.Invoked):
            parent_summary_builder.append_callee(intern(node.callee))
            if node.literals:
                parent_summary_builder.extend_literal(node.literals)
                child_literals_holder.append(node.literals)
        else:
            assert False

    try:
        sb = SummaryBuilder()
        dig_node(node, sb, [])
        sumry = sb.to_summary()
    except:
        sys.stderr.write("> warning: exception raised in get_node_summary:\n")
        pp = pprint.PrettyPrinter(indent=4, stream=sys.stderr)
        pp.pprint([jp.format_clzmsig(clzmsig) for clzmsig, recursive_cxt in stack])
        sys.stderr.write('\n')
        raise

    assert not stack
    return sumry


def node_summary_treecut(node):
    return get_node_summary(node, {}, use_callnode_label_with_depth=True)


def extract_node_summary_table(nodes):
    summary_table = {}  # (ClzMethodSig, recursive_context) -> Summary
    for node in nodes:
        get_node_summary(node, summary_table)
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
