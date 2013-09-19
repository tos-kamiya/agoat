#coding: utf-8

import re

from _utilities import quote

import jimp_parser as jp
import calltree as ct
import calltree_builder as cb
import calltree_sammarizer as cs


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
            target = TARGET_LITERAL
            if query_word.endswith('"'): query_word = query_word[:-1]
        else:
            target = TARGET_INVOKED
            query_word = quote(query_word.decode('utf-8').encode('utf-8'))
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
        self._count_patterns = len(self._invoked_patterns) + len(self._literal_patterns)
        self._invoked_pattern_words = [p.word for p in self._invoked_patterns]
        self._invoked_pattern_regexs = [p.regex for p in self._invoked_patterns]
        self._literal_pattern_words = [p.word for p in self._literal_patterns]
        self._literal_pattern_regexs = [p.regex for p in self._literal_patterns]

    def count(self):
        return self._count_patterns

    def is_fullfilled_by(self, sammary):
        for p in self._invoked_pattern_regexs:
            for w in sammary.invokeds:
                if p.search(w):
                    break  # for w
            else:
                return False
        for p in self._literal_pattern_regexs:
            for w in sammary.literals:
                if p.search(w):
                    break  # for w
            else:
                return False
        return True

    def is_partially_filled_by(self, sammary):
        for p in self._invoked_pattern_regexs:
            for w in sammary.invokeds:
                if p.search(w):
                    return True
        for p in self._literal_pattern_regexs:
            for w in sammary.literals:
                if p.search(w):
                    return True
        return False

    def has_matching_pattern_in(self, clz, msig, literals):
        for p in self._invoked_patterns:
            if p.regex.search(clz) or p.regex.search(msig):
                return True
        for p in self._literal_patterns:
            for w in literals:
                if p.regex.search(w):
                    return True
        return False

    def unmatched_patterns(self, sammary):
        unmatched_is = [p for p, r in zip(self._invoked_patterns, self._invoked_pattern_regexs) \
                if not any(r.search(w) for w in sammary.invokeds)]
        unmatched_ls = [p for p, r in zip(self._literal_patterns, self._literal_pattern_regexs) \
                if not any(r.search(w) for w in sammary.literals)]
        return unmatched_is + unmatched_ls

    def matched_patterns(self, sammary):
        matched_is = [p for p, r in zip(self._invoked_patterns, self._invoked_pattern_regexs) \
                if any(r.search(w) for w in sammary.invokeds)]
        matched_ls = [p for p, r in zip(self._invoked_patterns, self._literal_pattern_regexs) \
                if any(r.search(w) for w in sammary.literals)]
        return matched_is + matched_ls

    def matches_msig(self, msig):
        return any(p.search(msig) for p in self._invoked_pattern_regexs)

    def matches_receiver(self, clz):
        return any(p.search(clz) for p in self._invoked_pattern_regexs)

    def matches_literal(self, literal):
        return any(p.search(literal) for p in self._literal_pattern_regexs)


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


def gen_callnode_fullfills_query_predicate_w_memo(query, node_sammary_table):
    search_memo = {}
    def predicate(call_node):
        assert isinstance(call_node, ct.CallNode)
        node_label = cb.callnode_label(call_node)
        r = search_memo.get(node_label)
        if r is not None:
            return r
        sammary = node_sammary_table.get(node_label)
        result = sammary is not None and query.is_fullfilled_by(sammary)
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


def gen_treecut_fullfills_query_predicate(query):
    def predicate(treecut_with_callnode_depth):
        sammary = cs.get_node_sammary_wo_memoization(treecut_with_callnode_depth)
        return query.is_fullfilled_by(sammary)

    return predicate


def gen_treecut_partially_fills_query_predicate(query):
    def predicate(treecut_with_callnode_depth):
        sammary = cs.get_node_sammary_wo_memoization(treecut_with_callnode_depth)
        return query.is_partially_filled_by(sammary)

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


def update_cont_items_by_invoked(cont_items, invoked, query):
    cont_types, cont_method_names, cont_literals = cont_items
    clz, msig, literals = invoked[1], invoked[2], invoked[3]
    appeared_types = [clz, jp.methodsig_retv(msig)]
    appeared_types.extend(jp.methodsig_params(msig))
    invoked_cont = False
    for typ in appeared_types:
        if typ in cont_types:
            invoked_cont = True
        else:
            if query.matches_receiver(typ):
                invoked_cont = True
                cont_types.add(typ)
    m = jp.methodsig_name(msig)
    if m in cont_method_names:
        invoked_cont = True
    else:
        if query.matches_msig(m):
            invoked_cont = True
            cont_method_names.add(m)
    if literals:
        for lit in literals:
            if query.matches_literal(lit):
                invoked_cont = True
                cont_literals.add(lit)
    return invoked_cont


def extract_node_contribution(call_node, query):
    node_id_to_cont = {}
    cont_types = set()
    cont_method_names = set()
    cont_literals = set()
    cont_items = cont_types, cont_method_names, cont_literals

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
            invoked_cont = update_cont_items_by_invoked(cont_items, invoked, query)
            body_cont = mark_i(node.body)
            node_cont = invoked_cont or body_cont
        elif isinstance(node, tuple):
            assert node and node[0] in (jp.INVOKE, jp.SPECIALINVOKE)
            node_cont = update_cont_items_by_invoked(cont_items, node, query)
        else:
            assert False
        node_id_to_cont[id(node)] = node_cont
        return node_cont

    mark_i(call_node)
    return node_id_to_cont, cont_types, cont_method_names, cont_literals


# def extract_node_contributions(call_nodes, query):
#     node_id_to_cont = {}
#     cont_types = set()
#     cont_method_names = set()
#     cont_literals = set()
#     contribution_data = (node_id_to_cont, cont_types, cont_method_names, cont_literals)
#     for cn in call_nodes:
#         ni2c, ct, cm, cl = extract_node_contribution(cn, query)
#         if ni2c[id(cn)]:
#             node_id_to_cont.update(ni2c.iteritems())
#             cont_types.update(ct)
#             cont_method_names.update(cm)
#             cont_literals.update(cl)
#     return contribution_data
