#coding: utf-8

import re
import sys

from _utilities import quote, sort_uniq

import jimp_parser as jp
import calltree as ct
import calltree_builder as cb
import calltree_summarizer as cs


class QueryPattern(object):
    def __init__(self, word, ignore_case=False):
        uw = word.decode('utf-8')
        quoted_word = quote(uw.encode('unicode-escape'))
        backslash_doubled = quoted_word.replace(r"\u", r"\\u").replace(r"\U", r"\\U")
        self.regex = re.compile(backslash_doubled, re.IGNORECASE) if ignore_case else \
            re.compile(backslash_doubled)
        self.word = word

    def matches_type(self, typ):
        return False

    def matches_method(self, method):
        return False

    def matches_literal(self, w):
        return False

    def matches_callee(self, callee):
        return False


class TypeQueryPattern(QueryPattern):
    def matches_type(self, typ):
        return not not self.regex.search(typ)

    def matches_callee(self, callee):
        for i, t in enumerate(callee.split('\t')):  # clz, retv, method, param, ...
            if i == 2:
                continue
            if self.regex.search(t):
                return True
        else:
            return False


class MethodQueryPattern(QueryPattern):
    def matches_method(self, method):
        return not not self.regex.search(method)

    def matches_callee(self, callee):
        m = callee.split('\t')[2] # clz, retv, method, param, ...
        return self.regex.search(m)


class LiteralQueryPattern(QueryPattern):
    def matches_literal(self, w):
        return not not self.regex.search(w)


class AnyQueryPattern(QueryPattern):
    def matches_type(self, typ):
        return not not self.regex.search(typ)

    def matches_method(self, method):
        return not not self.regex.search(method)

    def matches_literal(self, w):
        return not not self.regex.search(w)

    def matches_callee(self, callee):
        for t in callee.split('\t'):  # clz, retv, method, param, ...
            if self.regex.search(t):
                return True
        else:
            return False

def compile_query(query_word, ignore_case=False):
    def _compile_i(target, query_word, ignore_case):
        pat = re.compile(query_word, re.IGNORECASE) if ignore_case else \
            re.compile(query_word)
        return QueryPattern(target, query_word, pat)

    if query_word.startswith('"'):
        query_word = query_word[1:]
        if query_word.endswith('"'):
            query_word = query_word[:-1]
        return LiteralQueryPattern(query_word, ignore_case)
    elif query_word.startswith('t.'):
        query_word = query_word[2:]
        return TypeQueryPattern(query_word, ignore_case)
    elif query_word.startswith('m.'):
        query_word = query_word[2:]
        return MethodQueryPattern(query_word, ignore_case)
    else:
        return AnyQueryPattern(query_word, ignore_case)


def types_in_clzmsig(clzmsig):
    types = [jp.clzmsig_clz(clzmsig)]
    types.append(jp.clzmsig_retv(clzmsig))
    types.extend(jp.clzmsig_params(clzmsig))
    types = ['void' if typ is None else typ for typ in types]
    types = sort_uniq(types)
    return types


class Query(object):
    def __init__(self, query_patterns):
        self._patterns = query_patterns

    def count(self):
        return len(self._patterns)

    def is_fullfilled_by(self, sumry):
        return not self.unmatched_patterns(sumry)

    def is_partially_filled_by(self, sumry):
        for suminv in sumry.callees:
            for p in self._patterns:
                if p.matches_callee(suminv):
                    return True
        for w in sumry.literals:
            for p in self._patterns:
                if p.matches_literal(w):
                    return True
        return False

    def has_matching_pattern_in(self, clzmsig, literals):
        for p in self._patterns:
            if p.matches_callee(clzmsig):
                return True
            for w in literals:
                if p.matches_literal(w):
                    return True
        return False

    def unmatched_patterns(self, sumry):
        remaining_patterns = self._patterns[:]
        for suminv in sumry.callees:
            remaining_patterns = [p for p in remaining_patterns if \
                    not p.matches_callee(suminv)]
            if not remaining_patterns:
                return []
        remaining_patterns = [p for p in remaining_patterns if \
                not any(p.matches_literal(w) for w in sumry.literals)]
        return remaining_patterns

    def matched_patterns(self, sumry):
        remaining_patterns = self._patterns[:]
        rems = []
        matcheds = []
        for suminv in sumry.callees:
            for p in remaining_patterns:
                (rems if not p.matches_callee(suminv) else \
                    matcheds).append(p)
            if not remaining_patterns:
                return matcheds
            remaining_patterns = rems
        for p in remaining_patterns:
            if any(p.matches_literal(w) for w in sumry.literals):
                matcheds.append(p)
        return matcheds

    def matches_method(self, method):
        return any(p.matches_method(method) for p in self._patterns)

    def matches_type(self, typ):
        return any(p.matches_type(typ) for p in self._patterns)

    def matches_literal(self, w):
        return any(p.matches_literal(w) for p in self._patterns)


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


def gen_callnode_fullfills_query_predicate_w_memo(query, node_summary_table):
    search_memo = {}
    def predicate(call_node):
        assert isinstance(call_node, ct.CallNode)
        node_label = cb.callnode_label(call_node)
        r = search_memo.get(node_label)
        if r is not None:
            return r
        sumry = node_summary_table.get(node_label)
        result = sumry is not None and query.is_fullfilled_by(sumry)
        search_memo[node_label] = result
        return result

    return predicate


def get_lower_bound_call_nodes(call_trees, predicate):
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
    callnode_memo = {}
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
                node_label = (node.invoked.callee, remaining_depth)
                cn = callnode_memo.get(node_label)
                if cn is None:
                    cn = ct.CallNode(node.invoked, remaining_depth, treecut_i(node.body, remaining_depth - 1))
                    callnode_memo[node_label] = cn
                return cn
            else:
                has_deeper_nodes[0] = True
                return node.invoked
        else:
            return node
    return treecut_i(node, depth)


def gen_treecut_fullfills_query_predicate(query):
    def predicate(treecut_with_callnode_depth):
        sumry = cs.get_node_summary(treecut_with_callnode_depth, {})
        return query.is_fullfilled_by(sumry)

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
    appeared_types = types_in_clzmsig(invoked.callee)
    invoked_cont = False
    for typ in appeared_types:
        if typ in cont_types:
            invoked_cont = True
        else:
            if query.matches_type(typ):
                invoked_cont = True
                cont_types.add(typ)
    m = jp.clzmsig_method(invoked.callee)
    if m in cont_method_names:
        invoked_cont = True
    else:
        if query.matches_method(m):
            invoked_cont = True
            cont_method_names.add(m)
    if invoked.literals:
        for lit in invoked.literals:
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
        node_cont = node_id_to_cont.get(id(node))
        if node_cont is None:
            if isinstance(node, list):
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
            elif isinstance(node, ct.Invoked):
                node_cont = update_cont_items_by_invoked(cont_items, node, query)
            else:
                assert False
            node_id_to_cont[id(node)] = node_cont
        return node_cont

    mark_i(call_node)
    return node_id_to_cont, cont_types, cont_method_names, cont_literals
