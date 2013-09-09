#coding: utf-8

import re

import _utilities

import jimp_parser as jp
from andor_tree import ORDERED_AND, ORDERED_OR
from andor_tree_query import Uncontributing, LengthNotDefined  # re-export
from calltree_builder import CALL
import andor_tree_query as atq


def calc_missing_query_words(summary, query_patterns):
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
            break  # for c, m
    return sorted(query_words_remaining.keys())


def build_query_pattern_list(query_words):
    if len(set(query_words)) != len(query_words):
        raise ValueError("duplicated query words")
    if not all(query_words):
        raise ValueError("empty string in query words")

    query_patterns = [(w, re.compile(w, re.IGNORECASE)) for w in query_words]
    return query_patterns


def find_lower_call_nodes(query_words, call_trees, node_summary_table):
    query_patterns = build_query_pattern_list(query_words)
    already_searched = set()
    def predicate_func(node):
        if isinstance(node, list) and node and node[0] == CALL:
            recursive_context = node[1]
            invoked = node[2]
            body = node[3]
            clz, msig = invoked[1], invoked[2]
            node_label = (clz, msig, recursive_context)
            if node_label in already_searched:
                return False
            already_searched.add(node_label)
            summary = node_summary_table.get(node_label)
            if summary is None:
                return False
            if not calc_missing_query_words(summary, query_patterns):
                lower_bound_nodes = atq.find_lower_bound_nodes(body, predicate_func)
                return atq.HookResult(lower_bound_nodes if lower_bound_nodes else [node])
            else:
                return atq.HookResult(atq.find_lower_bound_nodes(body, predicate_func))
        else:
            return atq.Undecided

    def get_call_node_label(call_node):
        assert isinstance(call_node, list) and call_node and call_node[0] == CALL
        recursive_context = call_node[1]
        invoked = call_node[2]
        clz, msig = invoked[1], invoked[2]
        return (clz, msig, recursive_context)

    call_nodes = []
    for call_tree in call_trees:
        call_nodes.extend(atq.find_lower_bound_nodes(call_tree, predicate_func))
    call_nodes = _utilities.sort_uniq(call_nodes, key=get_call_node_label)
    return call_nodes

def mark_uncontributing_nodes_w_call(query_words, call_node):
    query_patterns = build_query_pattern_list(query_words)
    len_query_patterns = len(query_patterns)
    call_node_memo = {}
    def predicate_func(node):
        if isinstance(node, list) and node and node[0] == CALL:
            recursive_context = node[1]
            invoked = node[2]
            body = node[3]
            clz, msig = invoked[1], invoked[2]
            node_label = (clz, msig, recursive_context)
            v = call_node_memo.get(node_label)
            if v is None:
                b = mark_uncontributing_nodes_w_call_i(body)
                recv_body_contributing = not isinstance(b, Uncontributing)
                if recv_body_contributing:
                    v = [CALL, recursive_context, invoked, b]
                else:
                    mw = calc_missing_query_words([(clz, msig)], query_patterns)
                    recv_clz_method_contributing = len(mw) < len_query_patterns
                    if recv_clz_method_contributing:
                        v = [CALL, recursive_context, invoked, Uncontributing([ORDERED_AND])]
                    else:
                        v = Uncontributing(node)
                call_node_memo[node_label] = v
            return atq.HookResult(v)
        elif isinstance(node, tuple) and node and node[0] in (jp.INVOKE, jp.SPECIALINVOKE):
            clz, msig = node[1], node[2]
            mw = calc_missing_query_words([(clz, msig)], query_patterns)
            return len(mw) < len_query_patterns
        else:
            return atq.Undecided
    def mark_uncontributing_nodes_w_call_i(node):
        return atq.mark_uncontributing_nodes(node, predicate_func)
    return mark_uncontributing_nodes_w_call_i(call_node)


def path_length(node):
    def weighting_func(node):
        if isinstance(node, list):
            assert node
            n0 = node[0]
            if n0 == CALL:
                return 1
            else:
                assert n0 in (ORDERED_AND, ORDERED_OR)
                return None
        else:
            return 1
    return atq.path_min_length(node, weighting_func)
