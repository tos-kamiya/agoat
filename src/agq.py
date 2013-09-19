#!/usr/bin/env python
#coding: utf-8

import argparse
import os
import sys
import pickle

from _utilities import open_w_default, sort_uniq

import _config as _c
import andor_tree as at
import calltree as ct
import calltree_builder as cb
import calltree_query as cq
from _calltree_data_formatter import DATATAG_CALL_TREES, DATATAG_NODE_SAMMARY, DATATAG_LINENUMBER_TABLE
from _calltree_data_formatter import format_call_tree_node_compact, init_ansi_color


def gen_expander_of_call_tree_to_paths(query):
    treecut_fullfills_query = cq.gen_treecut_fullfills_query_predicate(query)
    treecut_partially_fills_query = cq.gen_treecut_partially_fills_query_predicate(query)

    def expand_call_tree_to_paths(node):
        def expand_i(node):
            if isinstance(node, list):
                assert node
                n0 = node[0]
                if n0 == ct.ORDERED_OR:
                    paths = []
                    for subn in node[1:]:
                        ps = expand_i(subn)
                        if ps is not None:
                            for p in ps:
                                pnode = [ct.ORDERED_AND] + p
                                if p and treecut_partially_fills_query(pnode):
                                    paths.append(p)
                    if not paths:
                        return None
                    return paths
                elif n0 == ct.ORDERED_AND:
                    if len(node) == 1:
                        return None
                    pathssubs = []
                    for subn in node[1:]:
                        paths = expand_i(subn)
                        if paths is not None:
                            assert isinstance(paths, list)
                            pathssubs.append(paths)
                    if not pathssubs:
                        return None
                    paths = [[]]
                    for pathssub in pathssubs:
                        new_paths = []
                        for path in paths:
                            for p in pathssub:
                                new_path = path[:] + p
                                new_paths.append(new_path)
                        paths = new_paths
                        #paths = [(path[:] + p) for path in paths for p in pathssub]
                    return paths
            elif isinstance(node, ct.CallNode):
                if node.body:
                    body_paths = expand_i(node.body)
                    if body_paths:
                        paths = []
                        for bp in body_paths:
                            nbp = at.normalize_tree([ct.ORDERED_AND] + bp)
                            paths.append([ct.CallNode(node.invoked, node.recursive_cxt, nbp)])
                        return paths
                    else:
                        return [[ct.CallNode(node.invoked, node.recursive_cxt, None)]]
                else:
                    return [[node]]
            else:
                return [[node]]

        paths = expand_i(node)
        paths = [at.normalize_tree([ct.ORDERED_AND] + path) for path in paths]
        paths = [path for path in paths if treecut_fullfills_query(path)]
        return paths

    return expand_call_tree_to_paths


def remove_recursive_contexts(call_node):
    def remove_rc_i(node):
        if isinstance(node, list):
            assert node
            n0 = node[0]
            if n0 in (ct.ORDERED_AND, ct.ORDERED_OR):
                t = [n0]
                t.extend(remove_rc_i(subn) for subn in node[1:])
                return t
            else:
                assert False
        elif isinstance(node, ct.CallNode):
            return ct.CallNode(node.invoked, None, remove_rc_i(node.body))
        else:
            return node
    return remove_rc_i(call_node)


def remove_outermost_loc_info(call_node):
    invoked = call_node.invoked
    return ct.CallNode((invoked[0], invoked[1], invoked[2], invoked[3], None), call_node.recursive_cxt, call_node.body)


def search_in_call_trees(query, call_trees, node_sammary_table, max_depth, 
        removed_nodes_becauseof_limitation_of_depth=[None]):
    pred = cq.gen_callnode_fullfills_query_predicate_w_memo(query, node_sammary_table)
    call_nodes = cq.get_lower_bound_call_nodes(call_trees, pred)

    pred = cq.gen_treecut_fullfills_query_predicate(query)
    shallowers = filter(None, (cq.extract_shallowest_treecut(call_node, pred, max_depth) for call_node in call_nodes))
    removed_nodes_becauseof_limitation_of_depth[0] = len(call_nodes) - len(shallowers)

    contextlesses = [remove_outermost_loc_info(remove_recursive_contexts(cn)) for cn in shallowers]
    call_node_wo_rcs = sort_uniq(contextlesses, key=cb.callnode_label)

    return call_node_wo_rcs


def do_search(call_tree_file, query_words, ignore_case_query_words, output_file, line_number_table=None, 
        max_depth=-1, expand_to_path=True, fully_qualified_package_name=False, ansi_color=False,
        show_progress=False):
    log = sys.stderr.write if show_progress else None

    log and log("> loading index data\n")
    with open_w_default(call_tree_file, "rb", sys.stdin) as inp:
        # data = pickle.load(inp)  # very very slow in pypy
        data = pickle.loads(inp.read())
    call_trees = data[DATATAG_CALL_TREES]
    node_sammary_table = data[DATATAG_NODE_SAMMARY]
    del data

    clz_msig2conversion = None
    if line_number_table is not None:
        with open_w_default(line_number_table, "rb", sys.stdin) as inp:
            # data = pickle.load(inp)  # very very slow in pypy
            data = pickle.loads(inp.read())
            clz_msig2conversion = data[DATATAG_LINENUMBER_TABLE]
        del data

    log and log("> searching query in index\n")
    cq.check_query_word_list(query_words)
    query_patterns = []
    query_patterns.extend(cq.QueryPattern.compile(w) for w in query_words)
    query_patterns.extend(cq.QueryPattern.compile(w, ignore_case=True) for w in ignore_case_query_words)
    query = cq.Query(query_patterns)

    removed_nodes_becauseof_limitation_of_depth = [None]
    nodes = search_in_call_trees(query, call_trees, node_sammary_table, max_depth, 
            removed_nodes_becauseof_limitation_of_depth=removed_nodes_becauseof_limitation_of_depth)
    if not nodes:
        if removed_nodes_becauseof_limitation_of_depth[0] > 0:
            sys.stderr.write("> warning: all found code exceeds max call-tree depth. give option -D explicitly to show these code.\n")
        return

    if not expand_to_path:
        with open_w_default(output_file, "wb", sys.stdout) as out:
            for node in nodes:
                contribution_data = cq.extract_node_contribution(node, query)
                assert contribution_data[0][id(node)]
                out.write("---\n")
                format_call_tree_node_compact(node, out, contribution_data, clz_msig2conversion=clz_msig2conversion,
                        fully_qualified_package_name=fully_qualified_package_name, ansi_color=ansi_color)
        return

    log and log("> printing results\n")
    expand_call_tree_to_paths = gen_expander_of_call_tree_to_paths(query)
    path_nodes = []
    count_removed_path_becauseof_not_fullfilling_query = 0
    for node in nodes:
        pns = expand_call_tree_to_paths(node)
        if not pns:
            count_removed_path_becauseof_not_fullfilling_query += 1
        path_nodes.extend(pns)
    if not path_nodes:
        if count_removed_path_becauseof_not_fullfilling_query > 0:
            sys.stderr.write("> warning: no found paths includes all query words. give option -N to show such code instaed of path.\n")
        return

    with open_w_default(output_file, "wb", sys.stdout) as out:
        for pn in path_nodes:
            contribution_data = cq.extract_node_contribution(pn, query)
            out.write("---\n")
            format_call_tree_node_compact(pn, out, contribution_data, clz_msig2conversion=clz_msig2conversion,
                    fully_qualified_package_name=fully_qualified_package_name, ansi_color=ansi_color)


def main(argv):
    psr_q = argparse.ArgumentParser(description='agoat CLI query search')
    psr_q.add_argument('--version', action='version', version='%(prog)s ' + _c.VERSION)

    psr_q.add_argument('queryword', action='store', nargs='+', 
            help="""query words. put double quote(") before a word to search the word in string literals.""")
    psr_q.add_argument('-i', '--ignore-case-query-word', action='append')
    psr_q.add_argument('-c', '--call-tree', action='store', 
            help="call-tree file. '-' for standard input. (default '%s')" % _c.default_calltree_path,
            default=_c.default_calltree_path)
    psr_q.add_argument('-o', '--output', action='store', default='-')
    psr_q.add_argument('-l', '--line-number-table', action='store', 
            help="line-number table file. '-' for standard input. (default '%s')" % _c.default_linenumbertable_path,
            default=None)
    psr_q.add_argument('-D', '--max-depth', action='store', type=int, 
            help="max depth of subtree. -1 for unlimited depth. (default '%d')" % _c.defalut_max_depth_of_subtree,
            default=_c.defalut_max_depth_of_subtree)
    psr_q.add_argument('-N', '--node', action='store_true',
            help="show and-or-call tree node w/o expanding it to paths")
    color_choices=('always', 'never', 'auto')
    psr_q.add_argument('--color', '--colour', action='store', choices=color_choices, dest='color', 
            help="hilighting with ANSI color.",
            default='auto')
    psr_q.add_argument('-F', '--fully-qualified-package-name', action='store_true', default=False)
    psr_q.add_argument("--progress", action='store_true',
            help="show progress to standard output",
            default=False)

    args = psr_q.parse_args(argv[1:])
    line_number_table = None
    if args.line_number_table is not None:
        line_number_table = args.line_number_table
    else:
        if os.path.exists(_c.default_linenumbertable_path):
            line_number_table = _c.default_linenumbertable_path
    ansi_color = sys.stdout.isatty() if args.color == 'auto' else args.color == 'always'
    if ansi_color:
        init_ansi_color()
    if not args.ignore_case_query_word: 
        ignore_case_query_words = []
    else:
        ignore_case_query_words = args.ignore_case_query_word
    do_search(args.call_tree, args.queryword, ignore_case_query_words, args.output,  line_number_table, 
            max_depth=args.max_depth, expand_to_path=not args.node, 
            fully_qualified_package_name=args.fully_qualified_package_name, ansi_color=ansi_color,
            show_progress=args.progress)


if __name__ == '__main__':
    main(sys.argv)