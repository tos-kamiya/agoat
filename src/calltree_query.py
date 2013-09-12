#coding: utf-8

import re

import calltree as ct
import calltree_builder as cb
import calltree_summarizer as cs


TARGET_METHOD = 'target_method'
TARGET_LITERAL = 'target_literal'


class QueryPattern(object):
    def __init__(self, target, word, regex):
        self.target = target
        self.word = word
        self.regex = regex

    def __repr__(self):
        return "QueryPattern(%s,%s,%s)" % (repr(self.target), repr(self.word), repr(self.regex))


def missing_query_patterns(summary, query_patterns):
    remainings = query_patterns[:]
    for s in summary:
        found_index = None
        if isinstance(s, tuple):
            c, m = s
            for i, p in enumerate(remainings):
                if p.target == TARGET_METHOD:
                    if p.regex.search(c) or p.regex.search(m):
                        found_index = i
                        break  # for i, p
        else:
            for i, p in enumerate(remainings):
                if p.target == TARGET_LITERAL:
                    if p.regex.search(s):
                        found_index = i
                        break  # for p
        if found_index is not None:
            del remainings[found_index]
        if not remainings:
            return []
    return remainings


def build_query_pattern_list(query_words, ignore_case=False):
    if len(set(query_words)) != len(query_words):
        raise ValueError("duplicated query words")
    if not all(query_words):
        raise ValueError("empty string in query words")

    if ignore_case:
        def re_compile(w): return re.compile(w, re.IGNORECASE)
    else:
        def re_compile(w): return re.compile(w)

    query_patterns = []
    for w in query_words:
        assert w
        if w.startswith('"'):
            if w.endswith('"'): w = w[:-1]
            qp = QueryPattern(TARGET_LITERAL, w, re_compile(w))
        else:
            qp = QueryPattern(TARGET_METHOD, w, re_compile(w))
        query_patterns.append(qp)
    return query_patterns


def get_direct_sub_callnodes_of_body_node(body_node):
    if isinstance(body_node, list):
        assert body_node
        n0 = body_node[0]
        if n0 in (ct.ORDERED_AND, ct.ORDERED_OR):
            scs = []
            for subn in body_node[1:]:
                scs.extend(get_direct_sub_callnodes_of_body_node(subn))
            return scs
        else:
            assert False
    elif isinstance(body_node, ct.CallNode):
        return [body_node]
    else:
        return []


def make_callnode_fullfill_query_predicate_w_memo(query_patterns, node_summary_table):
    search_memo = {}
    def predicate(call_node):
        assert isinstance(call_node, ct.CallNode)
        node_label = cb.callnode_label(call_node)
        r = search_memo.get(node_label)
        if r is not None:
            return r
        summary = node_summary_table.get(node_label)
        if summary is None:
            result = False
        else:
            result = not missing_query_patterns(summary, query_patterns)
        r = search_memo[node_label] = result
        return r

    return predicate


def get_lower_bound_call_nodes(call_trees, predicate):
    def get_recv_msig(call_node):
        assert isinstance(call_node, ct.CallNode)
        invoked = call_node.invoked
        clz, msig = invoked[1], invoked[2]
        return (clz, msig)

    already_searched_call_node_labels = set()
    lower_call_nodes = []
    def search_i(call_node):
        node_label = cb.callnode_label(call_node)
        if node_label in already_searched_call_node_labels:
            return
        subcs = get_direct_sub_callnodes_of_body_node(call_node.body)
        any_subc_fullfill_query = False
        for subc in subcs:
            if predicate(subc):
                any_subc_fullfill_query = True
                search_i(subc)
        if not any_subc_fullfill_query:
            lower_call_nodes.append(call_node)
        already_searched_call_node_labels.add(node_label)

    for call_tree in call_trees:
        assert isinstance(call_tree, ct.CallNode)
        if predicate(call_tree):
            search_i(call_tree)

    return lower_call_nodes


def treecut_with_callnode_depth(node, depth, has_deeper_nodes=[None]):
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
                has_deeper_nodes[0] = True
                return node.invoked
        else:
            return node
    return treecut_i(node, depth)


def make_treecut_fullfill_query_predicate(query_patterns):
    def predicate(treecut_with_callnode_depth):
        summary = cs.get_node_summary_wo_memoization(treecut_with_callnode_depth)
        missings = missing_query_patterns(summary, query_patterns)
        return not missings

    return predicate


def extract_shallowest_treecut(call_node, predicate, max_depth=-1):
    assert isinstance(call_node, ct.CallNode)

    depth = 1
    while max_depth < 0 or depth < max_depth:
        has_further_deep_nodes = [False]
        tc = treecut_with_callnode_depth(call_node, depth, has_further_deep_nodes)
        if predicate(tc):
            return tc
        assert has_further_deep_nodes[0]
        depth += 1

    # not found
    return None
