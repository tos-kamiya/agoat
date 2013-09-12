#coding: utf-8

import re

import jimp_parser as jp
import calltree as ct
import calltree_builder as cb
import calltree_summarizer as cs


TARGET_INVOKED = 'target_invoked'
TARGET_LITERAL = 'target_literal'


class QueryPattern(object):
    def __init__(self, target, word, regex):
        self.target = target
        self.word = word
        self.regex = regex

    def __repr__(self):
        return "QueryPattern(%s,%s,%s)" % (repr(self.target), repr(self.word), repr(self.regex))

    @staticmethod
    def compile(query_word, ignore_case=False):
        if query_word.startswith('"'):
            if query_word.endswith('"'): query_word = query_word[:-1]
            target = TARGET_LITERAL
        else:
            target = TARGET_INVOKED
        pat = re.compile(query_word, re.IGNORECASE) if ignore_case else \
            re.compile(query_word)
        return QueryPattern(target, query_word, pat)


class Query(object):
    def __init__(self, query_patterns):
        self._invoked_patterns = []
        self._literal_patterns = []
        for p in query_patterns:
            if p.target == TARGET_INVOKED:
                self._invoked_patterns.append(p)
            elif p.target == TARGET_LITERAL:
                self._literal_patterns.append(p)

    def count(self):
        return len(self._invoked_patterns) + len(self._literal_patterns)

    def is_fullfilled_by(self, summary):
        return not self.unmatched_patterns(summary)

    def unmatched_patterns(self, summary):
        invokeds = []
        literals = []
        for s in summary:
            if isinstance(s, tuple):
                c, m = s
                invokeds.append(c)
                invokeds.append(m)
            else:
                literals.append(s)

        unmatched_is = [p for p in self._invoked_patterns if not any(p.regex.search(w) for w in invokeds)]
        unmatched_ls = [p for p in self._literal_patterns if not any(p.regex.search(w) for w in literals)]
        return unmatched_is + unmatched_ls

    def matches_invoked(self, clz, msig):
        for p in self._invoked_patterns:
            if clz and p.regex.search(clz) or msig and p.regex.search(msig):
                return True
        return False

    def matches_literals(self, literals):
        for lit in literals:
            for p in self._literal_patterns:
                if p.regex.search(lit):
                    return True
        return False


def check_query_word_list(query_words):
    if len(set(query_words)) != len(query_words):
        raise ValueError("duplicated query words")
    if not all(query_words):
        raise ValueError("empty string in query words")


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


def make_callnode_fullfill_query_predicate_w_memo(query, node_summary_table):
    search_memo = {}
    def predicate(call_node):
        assert isinstance(call_node, ct.CallNode)
        node_label = cb.callnode_label(call_node)
        r = search_memo.get(node_label)
        if r is not None:
            return r
        summary = node_summary_table.get(node_label)
        result = summary is not None and query.is_fullfilled_by(summary)
        search_memo[node_label] = result
        return result

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


def make_treecut_fullfill_query_predicate(query):
    def predicate(treecut_with_callnode_depth):
        summary = cs.get_node_summary_wo_memoization(treecut_with_callnode_depth)
        return query.is_fullfilled_by(summary)

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


def extract_node_contribution(call_node, query):
    node_id_to_cont = {}
    cont_clzs = set()
    cont_msigs = set()
    cont_literals = set()

    def update_about_invoked(invoked):
        clz, msig, literals = invoked[1], invoked[2], invoked[3]
        clz_cont = clz in cont_clzs or query.matches_invoked(clz, None)
        clz_cont and cont_clzs.add(clz)
        msig_cont = msig in cont_msigs or query.matches_invoked(None, msig)
        msig_cont and cont_msigs.add(msig)
        literal_cont = (not not literals) and query.matches_literals(literals)
        literal_cont and cont_literals.add(literals)
        return clz_cont, msig_cont, literal_cont

    def mark_i(node):
        if node is None:
            return False  # None is always uncontributing
        elif isinstance(node, list):
            assert node
            n0 = node[0]
            assert n0 in (ct.ORDERED_AND, ct.ORDERED_OR)
            node_cont = False
            for item in node[1:]:
                if mark_i(item):
                    node_cont = True
                    #  don't break for item
        elif isinstance(node, ct.CallNode):
            invoked = node.invoked
            clz_cont, msig_cont, literal_cont = update_about_invoked(invoked)
            recv_body_cont = mark_i(node.body)
            node_cont = clz_cont or msig_cont or literal_cont or recv_body_cont
        elif isinstance(node, tuple):
            assert node and node[0] in (jp.INVOKE, jp.SPECIALINVOKE)
            clz_cont, msig_cont, literal_cont = update_about_invoked(node)
            node_cont = clz_cont or msig_cont or literal_cont
        else:
            assert False
        node_id_to_cont[id(node)] = node_cont
        return node_cont

    mark_i(call_node)
    return node_id_to_cont, cont_clzs, cont_msigs, cont_literals


def extract_node_contributions(call_nodes, query):
    node_id_to_cont = {}
    cont_clzs = set()
    cont_msigs = set()
    cont_literals = set()
    contribution_data = (node_id_to_cont, cont_clzs, cont_msigs, cont_literals)
    for cn in call_nodes:
        ni2c, cc, cm, cl = extract_node_contribution(cn, query)
        if ni2c[id(cn)]:
            node_id_to_cont.update(ni2c.iteritems())
            cont_clzs.update(cc)
            cont_msigs.update(cm)
            cont_literals.update(cl)
    return contribution_data
