#coding: utf-8

import re
import itertools

import jimp_parser as jp
import calltree as ct
from andor_tree_query import Uncontributing # re-export
import andor_tree_query as atq
import calltree_builder as cb
import calltree_summarizer as cs

def missing_query_words(summary, query_patterns):
    query_words_remaining = dict((w, r) for w, r in query_patterns)
    for c, m in summary:
        found = False
        for qw, qr in query_words_remaining.iteritems():
            if qr.search(c) or qr.search(m):
                found = True
                break  # for qw
        if found:
            del query_words_remaining[qw]
        if not query_words_remaining:
            return []
    return query_words_remaining.keys()


def build_query_pattern_list(query_words, ignore_case=False):
    if len(set(query_words)) != len(query_words):
        raise ValueError("duplicated query words")
    if not all(query_words):
        raise ValueError("empty string in query words")

    if ignore_case:
        query_patterns = [(w, re.compile(w, re.IGNORECASE)) for w in query_words]
    else:
        query_patterns = [(w, re.compile(w)) for w in query_words]
    return query_patterns


def find_lower_call_nodes(query_patterns, call_trees, node_summary_table):
    already_searched = set()
    def predicate_func(node):
        if isinstance(node, ct.CallNode):
            invoked = node.invoked
            node_label = cb.callnode_label(node)
            if node_label in already_searched:
                return False
            already_searched.add(node_label)
            summary = node_summary_table.get(node_label)
            if summary is None:
                return False
            if not missing_query_words(summary, query_patterns):
                lower_bound_nodes = atq.find_lower_bound_nodes(node.body, predicate_func)
                return atq.HookResult(lower_bound_nodes if lower_bound_nodes else [node])
            else:
                return atq.HookResult(atq.find_lower_bound_nodes(node.body, predicate_func))
        else:
            return atq.Undecided

    def get_recv_msig(call_node):
        assert isinstance(call_node, ct.CallNode)
        invoked = call_node.invoked
        clz, msig = invoked[1], invoked[2]
        return (clz, msig)

    call_nodes = []
    for call_tree in call_trees:
        call_nodes.extend(atq.find_lower_bound_nodes(call_tree, predicate_func))
    call_nodes.sort(key=get_recv_msig)
    uniq_call_nodes = []
    for k, g in itertools.groupby(call_nodes, key=get_recv_msig):
        uniq_call_nodes.append(g.next())
    return uniq_call_nodes


def treecut(node, depth, has_further_deep_nodes=[None]):
    def treecut_i(node, remaining_depth):
        if isinstance(node, list):
            assert node
            n0 = node[0]
            if n0 in (ct.ORDERED_AND, ct.ORDERED_OR):
                t = [n0]
                for subn in node[1:]:
                    t.append(treecut_i(subn, remaining_depth))
                return t
            else:
                assert False
        elif isinstance(node, ct.CallNode):
            if remaining_depth > 0:
                cn = ct.CallNode(node.invoked, node.recursive_cxt, treecut_i(node.body, remaining_depth - 1))
                return cn
            else:
                has_further_deep_nodes[0] = True
                return node.invoked
        else:
            return node
    return treecut_i(node, depth)


def extract_shallowest_treecut(call_node, query_patterns, max_depth=-1):
    assert isinstance(call_node, ct.CallNode)

    depth = 1
    while max_depth < 0 or depth < max_depth:
        has_further_deep_nodes = [False]
        tc = treecut(call_node, depth, has_further_deep_nodes)
        summary = cs.summarize_node(tc)
        m = missing_query_words(summary, query_patterns)
        if not m:
            return tc
        assert has_further_deep_nodes[0]
        depth += 1

    # not found
    return None

def mark_uncontributing_nodes_w_call(call_node, query_patterns):
    len_query_patterns = len(query_patterns)
    call_node_memo = {}
    def predicate_func(node):
        if isinstance(node, ct.CallNode):
            invoked = node.invoked
            clz_msig = invoked[1], invoked[2]
            node_label = cb.callnode_label(node)
            v = call_node_memo.get(node_label)
            if v is None:
                b = mark_uncontributing_nodes_w_call_i(node.body)
                recv_body_contributing = not isinstance(b, Uncontributing)
                if recv_body_contributing:
                    v = ct.CallNode(node.invoked, node.recursive_cxt, b)
                else:
                    if len(missing_query_words([(clz_msig)], query_patterns)) < len_query_patterns:
                        v = ct.CallNode(node.invoked, node.recursive_cxt, Uncontributing([ct.ORDERED_AND]))
                    else:
                        v = Uncontributing(node)
                call_node_memo[node_label] = v
            return atq.HookResult(v)
        elif isinstance(node, tuple) and node and node[0] in (jp.INVOKE, jp.SPECIALINVOKE):
            clz, msig = node[1], node[2]
            return len(missing_query_words([(clz, msig)], query_patterns)) < len_query_patterns
        else:
            return atq.Undecided
    def mark_uncontributing_nodes_w_call_i(node):
        return atq.mark_uncontributing_nodes(node, predicate_func)
    return mark_uncontributing_nodes_w_call_i(call_node)


# def path_length(node):
#     def weighting_func(node):
#         if isinstance(node, list):
#             assert node
#             n0 = node[0]
#             if n0 == CALL:
#                 return 1
#             else:
#                 assert n0 in (ORDERED_AND, ORDERED_OR)
#                 return None
#         else:
#             return 1
#     return atq.path_min_length(node, weighting_func)
