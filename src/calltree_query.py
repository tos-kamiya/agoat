#coding: utf-8

import re

from _utilities import quote, sort_uniq

import jimp_parser as jp
import calltree as ct
import calltree_builder as cb
import calltree_sammarizer as cs


TARGET_TYPE = 'target_type'
TARGET_METHOD = 'target_method'
TARGET_LITERAL = 'target_literal'


class QueryPattern(object):
    def __init__(self, target, word, regex):
        self.target = target
        self.word = word
        self.regex = regex

    def __repr__(self):
        return "QueryPattern(%s,%s,%s)" % (repr(self.target), repr(self.word), repr(self.regex))

    @staticmethod
    def _compile_i(target, query_word, ignore_case):
        pat = re.compile(query_word, re.IGNORECASE) if ignore_case else \
            re.compile(query_word)
        return QueryPattern(target, query_word, pat)

    @staticmethod
    def compile(query_word, ignore_case=False):
        if query_word.startswith('"'):
            query_word = query_word[1:]
            if query_word.endswith('"'):
                query_word = query_word[:-1]
            return QueryPattern._compile_i(TARGET_LITERAL, query_word, ignore_case)
        elif query_word.startswith('t.'):
            query_word = query_word[2:]
            query_word = quote(query_word.decode('utf-8').encode('utf-8'))
            return QueryPattern._compile_i(TARGET_TYPE, query_word, ignore_case)
        elif query_word.startswith('m.'):
            query_word = query_word[2:]
            query_word = quote(query_word.decode('utf-8').encode('utf-8'))
            return QueryPattern._compile_i(TARGET_METHOD, query_word, ignore_case)
        else:
            # drop to method pattern
            query_word = quote(query_word.decode('utf-8').encode('utf-8'))
            return QueryPattern._compile_i(TARGET_METHOD, query_word, ignore_case)


def types_in_sammary_invoked(sammary_invoked):
    fields = sammary_invoked.split('\t')  # clz, retv, method, param, ...
    del fields[2]
    return sort_uniq(fields)


def method_in_sammary_invoked(sammary_invoked):
    return sammary_invoked.split('\t')[2]


def types_in_msig(msig):
    types = [jp.methodsig_retv(msig)]
    types.extend(jp.methodsig_params(msig))
    return types


class Query(object):
    def __init__(self, query_patterns):
        self._type_patterns = []
        self._method_patterns = []
        self._literal_patterns = []
        for p in query_patterns:
            patterns = None
            if p.target == TARGET_TYPE:
                patterns = self._type_patterns
            elif p.target == TARGET_METHOD:
                patterns = self._method_patterns
            elif p.target == TARGET_LITERAL:
                patterns = self._literal_patterns
            else:
                assert False
            patterns.append(p)
        self._count_patterns = sum(map(len, [
                self._type_patterns, self._method_patterns, self._literal_patterns]))
        if self._type_patterns:
            self._type_words, self._type_regexs = \
                    zip(*[(p.word, p.regex) for p in self._type_patterns])
        else:
            self._type_words, self._type_regexs = [], []
        if self._method_patterns:
            self._method_words, self._method_regexs = \
                    zip(*[(p.word, p.regex) for p in self._method_patterns])
        else:
            self._method_words, self._method_regexs = [], []
        if self._literal_patterns:
            self._literal_words, self._literal_regexs = \
                    zip(*[(p.word, p.regex) for p in self._literal_patterns])
        else:
            self._literal_words, self._literal_regexs = [], []

    def count(self):
        return self._count_patterns

    def is_fullfilled_by(self, sammary):
        remaining_type_regexs = self._type_regexs[:]
        if remaining_type_regexs:
            for saminv in sammary.invokeds:
                types = types_in_sammary_invoked(saminv)
                remaining_type_regexs = [r for r in remaining_type_regexs \
                        if not any(r.search(typ) for typ in types)]
                if not remaining_type_regexs:
                    break  # for saminv
            else:
                return False
        reamining_method_regexs = self._method_regexs[:]
        if reamining_method_regexs:
            for saminv in sammary.invokeds:
                method = method_in_sammary_invoked(saminv)
                reamining_method_regexs = [r for r in reamining_method_regexs \
                        if not r.search(method)]
                if not reamining_method_regexs:
                    break  # for saminv
            else:
                return False
        if self._literal_regexs:
            for p in self._literal_regexs:
                for w in sammary.literals:
                    if p.search(w):
                        break  # for w
                else:
                    return False
        return True

    def is_partially_filled_by(self, sammary):
        if self._count_patterns == 0:
            return True
        for saminv in sammary.invokeds:
            types = types_in_sammary_invoked(saminv)
            for typ in types:
                for r in self._type_regexs:
                    if r.search(typ):
                        return True
        for saminv in sammary.invokeds:
            method = method_in_sammary_invoked(saminv)
            for r in self._method_regexs:
                if r.search(method):
                    return True
        for p in self._literal_regexs:
            for w in sammary.literals:
                if p.search(w):
                    return True
        return False

    def has_matching_pattern_in(self, clz, msig, literals):
        for p in self._type_regexs:
            if p.search(clz):
                return True
            if p.search(jp.methodsig_retv(msig)):
                return True
            if any(p.search(a) for a in jp.methodsig_params(msig)):
                return True
        for p in self._method_regexs:
            if p.search(jp.methodsig_name(msig)):
                return True
        for p in self._literal_patterns:
            for w in literals:
                if p.regex.search(w):
                    return True
        return False

    def unmatched_patterns(self, sammary):
        remaining_types = zip(self._type_patterns, self._type_regexs)
        for saminv in sammary.invokeds:
            types = types_in_sammary_invoked(saminv)
            remaining_types = [pr for pr in remaining_types \
                    if not any(pr[1].search(typ) for typ in types)]
            if not remaining_types:
                break  # for saminv
        remaining_methods = zip(self._method_patterns, self._method_regexs)
        for saminv in sammary.invokeds:
            method = method_in_sammary_invoked(saminv)
            remaining_methods = [pr for pr in remaining_methods \
                    if not pr[1].search(method)]
            if not remaining_methods:
                break  # for saminv
        remaining_literals = zip(self._literal_patterns, self._literal_regexs)
        for w in sammary.literals:
            remaining_literals = [pr for pr in remaining_literals \
                    if not pr[1].search(w)]
            if not remaining_literals:
                break  # for w
        return [pr[0] for pr in remaining_types + remaining_methods + remaining_literals]

    def matched_patterns(self, sammary):
        remaining_types = zip(self._type_patterns, self._type_regexs)
        matched_type_patterns = []
        for saminv in sammary.invokeds:
            types = types_in_sammary_invoked(saminv)
            rems = []
            for pr in remaining_types:
                if any(pr[1].search(typ) for typ in types):
                    matched_type_patterns.append(pr[0])
                    break  # for pr
            else:
                rems.append(pr)
            if not rems:
                break  # for saminv
            remaining_types = rems
        remaining_methods = zip(self._method_patterns, self._method_regexs)
        matched_method_patterns = []
        for saminv in sammary.invokeds:
            method = method_in_sammary_invoked(saminv)
            rems = []
            for pr in remaining_methods:
                if pr[1].search(method):
                    matched_method_patterns.append(pr[0])
                    break  # for pr
            else:
                rems.append(pr)
            if not rems:
                break  # for saminv
            remaining_methods = rems
        remaining_literals = zip(self._literal_patterns, self._literal_regexs)
        matched_literal_patterns = []
        for w in sammary.literals:
            rems = []
            for pr in remaining_literals:
                if pr[1].search(w):
                    matched_literal_patterns.append(pr[0])
                    break  # for pr
            else:
                rems.append(pr)
            if not rems:
                break  # for w
            remaining_literals = rems
        return matched_type_patterns + matched_method_patterns + matched_literal_patterns

    def matches_method(self, method):
        for r in self._method_regexs:
            if r.search(method):
                return True
        return False

    def matches_msig(self, msig):
        for r in self._type_regexs:
            if any(r.search(typ) for typ in types_in_msig(msig)):
                return True
        for r in self._method_regexs:
            if any(r.search(jp.methodsig_name(msig))):
                return True
        return False

    def matches_receiver(self, clz):
        for r in self._type_regexs:
            if r.search(clz):
                return True
        return False

    def matches_literal(self, literal):
        return any(p.search(literal) for p in self._literal_regexs)


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
                node_label = (node.invoked[1], node.invoked[2], remaining_depth)
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
        sam = cs.get_node_sammary(treecut_with_callnode_depth, {})
        return query.is_fullfilled_by(sam)

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
        if query.matches_method(m):
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
            elif isinstance(node, tuple):
                assert node and node[0] in (jp.INVOKE, jp.SPECIALINVOKE)
                node_cont = update_cont_items_by_invoked(cont_items, node, query)
            else:
                assert False
            node_id_to_cont[id(node)] = node_cont
        return node_cont

    mark_i(call_node)
    return node_id_to_cont, cont_types, cont_method_names, cont_literals
