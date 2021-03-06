#coding: utf-8

import argparse
import os
import sys
import pickle

from _utilities import sort_uniq, STDOUT, STDIN, open_gziped_file_when_available

from . import _config as _c
from . import andor_tree as at
from . import calltree as ct
from . import calltree_summary as cs
from . import calltree_builder as cb
from . import calltree_query as cq
from ._calltree_data_formatter import DATATAG_ENTRY_POINTS, DATATAG_CALL_TREES, DATATAG_NODE_SUMMARY, DATATAG_LINENUMBER_TABLE
from .jimp_parser import format_clzmsig
from ._calltree_data_formatter import format_call_tree_node_compact, init_ansi_color


def gen_expander_of_call_tree_to_paths(query):
    def expand_call_tree_to_paths(node):
        def expand_i(node, memo):
            if isinstance(node, list):
                assert node
                n0 = node[0]
                if n0 == ct.ORDERED_OR:
                    paths = []
                    for subn in node[1:]:
                        ps = expand_i(subn, memo)
                        if ps is not None:
                            paths.extend(ps)
                    if not paths:
                        return None
                    paths = sort_uniq(paths)
                    return paths
                elif n0 == ct.ORDERED_AND:
                    if len(node) == 1:
                        return None
                    pathssubs = []
                    for subn in node[1:]:
                        paths = expand_i(subn, memo)
                        if paths is not None:
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
                node_label = cb.callnode_label(node)
                paths = memo.get(node_label)
                if paths is None:
                    if node.body:
                        body_paths = expand_i(node.body, {})
                        if body_paths:
                            paths = []
                            for bp in body_paths:
                                nbp = at.normalize_tree([ct.ORDERED_AND] + bp)
                                paths.append([ct.CallNode(node.invoked, node.recursive_cxt, nbp)])
                        else:
                            paths = [[ct.CallNode(node.invoked, node.recursive_cxt, None)]]
                    else:
                        paths = [[node]]
                    memo[node_label] = paths[:]
                    return paths
            elif isinstance(node, ct.Invoked):
                if query.has_matching_pattern_in(node.callee, node.literals):
                    return [[node]]
                return None
            else:
                assert False

        paths = expand_i(node, {})
        paths = sort_uniq(paths)
        paths = [at.normalize_tree([ct.ORDERED_AND] + path) for path in paths]
        paths = [path for path in paths if query.is_fulfilled_by(cs.node_summary_treecut(path))]
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
    return ct.CallNode(ct.Invoked(invoked.cmd, invoked.callee, invoked.literals, None), 
            call_node.recursive_cxt, call_node.body)


def search_in_call_trees(query, call_trees, node_summary_table, max_depth,
        removed_nodes_becauseof_limitation_of_depth=None):
    if removed_nodes_becauseof_limitation_of_depth:
        removed_nodes_becauseof_limitation_of_depth = [None]
    pred = cq.gen_callnode_fulfills_query_predicate_w_memo(query, node_summary_table)
    call_nodes = cq.get_lower_bound_call_nodes(call_trees, pred)

    shallowers = list(filter(None, (cq.extract_shallowest_treecut(call_node, query, max_depth) for call_node in call_nodes)))
    removed_nodes_becauseof_limitation_of_depth[0] = len(call_nodes) - len(shallowers)

    contextlesses = [remove_outermost_loc_info(remove_recursive_contexts(cn)) for cn in shallowers]
    call_node_wo_rcs = sort_uniq(contextlesses, key=cb.callnode_label)

    return call_node_wo_rcs


def remove_uncontributing_nodes(node, node_id_to_cont):
    def remove_i(node):
        if not node_id_to_cont.get(id(node)):
            return None
        if isinstance(node, list):
            assert node
            n0 = node[0]
            if n0 in (ct.ORDERED_AND, ct.ORDERED_OR):
                buf = [n0]
                for subn in node[1:]:
                    b = remove_i(subn)
                    if b:
                        buf.append(b)
                return buf
            else:
                assert False
        elif isinstance(node, ct.CallNode):
            buf = remove_i(node.body)
            if buf:
                return ct.CallNode(node.invoked, node.recursive_cxt, buf)
            else:
                return node.invoked
        elif isinstance(node, ct.Invoked):
            return node
        else:
            assert None
    return remove_i(node)


def do_search(call_tree_file, node_summary_file, query_words, ignore_case_query_words, output_file, line_number_table=None, 
        max_depth=-1, output_form='path', fully_qualified_package_name=False, ansi_color=False,
        show_progress=False):
    log = sys.stderr.write if show_progress else None

    cq.check_query_word_list(query_words)
    query_patterns = []
    for w in query_words:
        query_patterns.append(cq.compile_query(w))
    for w in ignore_case_query_words:
        query_patterns.append(cq.compile_query(w, ignore_case=True))
    query = cq.Query(query_patterns)

    log and log("> loading call trees\n")
    with open_gziped_file_when_available(call_tree_file, "rb") as inp:
        # data = pickle.load(inp)  # very very slow in pypy
        data = pickle.loads(inp.read())
    call_trees = data[DATATAG_CALL_TREES]
    ce = data[DATATAG_ENTRY_POINTS]
    del data

    log and log("> loading summary table\n")
    with open_gziped_file_when_available(node_summary_file, "rb") as inp:
        # data = pickle.load(inp)  # very very slow in pypy
        data = pickle.loads(inp.read())
    node_summary_table = data[DATATAG_NODE_SUMMARY]
    ne = data[DATATAG_ENTRY_POINTS]
    del data
    if ce != ne:
        raise ValueError("inconsistency between call-trees data and node-summary table")

    clz_msig2conversion = None
    if line_number_table is not None:
        with open_gziped_file_when_available(line_number_table, "rb") as inp:
            # data = pickle.load(inp)  # very very slow in pypy
            data = pickle.loads(inp.read())
            clz_msig2conversion = data[DATATAG_LINENUMBER_TABLE]
        del data

    log and log("> searching query in index\n")
    removed_nodes_becauseof_limitation_of_depth = [None]
    nodes = search_in_call_trees(query, call_trees, node_summary_table, max_depth, 
            removed_nodes_becauseof_limitation_of_depth=removed_nodes_becauseof_limitation_of_depth)

    if output_form == 'callnode':
        clzmsigs = [n.invoked.callee for n in nodes]
        clzmsigs.sort()
        with open(output_file, "wb") as out:
            for cm in clzmsigs:
                out.write('%s\n' % format_clzmsig(cm))
        return

    if not nodes:
        if removed_nodes_becauseof_limitation_of_depth[0] > 0:
            sys.stderr.write("> warning: all found code exceeds max call-tree depth." +
                    " give option -d explicitly to show these code.\n")
        return

    for ni in range(len(nodes)):
        node = nodes[ni]
        node_id_to_cont = cq.extract_node_contribution(node, query)
        nodes[ni] = remove_uncontributing_nodes(node, node_id_to_cont)

    if output_form == 'treecut':
        with open(output_file, "wb") as out:
            for node in nodes:
                out.write("---\n")
                format_call_tree_node_compact(node, out, query,
                        clz_msig2conversion=clz_msig2conversion, 
                        fully_qualified_package_name=fully_qualified_package_name, 
                        ansi_color=ansi_color)
        return

    assert output_form == 'path'
    log and log("> printing results\n")
    expand_call_tree_to_paths = gen_expander_of_call_tree_to_paths(query)
    path_nodes = []
    count_removed_path_becauseof_not_fulfilling_query = 0
    for node in nodes:
        pns = expand_call_tree_to_paths(node)
        if not pns:
            count_removed_path_becauseof_not_fulfilling_query += 1
        path_nodes.extend(pns)
    if not path_nodes:
        if count_removed_path_becauseof_not_fulfilling_query > 0:
            sys.stderr.write("> warning: no found paths includes all query words." +
                    " use '-f treecut' to show them as treecut, not as path.\n")
        return

    with open(output_file, "wb") as out:
        for pn in path_nodes:
            out.write("---\n")
            format_call_tree_node_compact(pn, out, query,
                    clz_msig2conversion=clz_msig2conversion,
                    fully_qualified_package_name=fully_qualified_package_name, 
                    ansi_color=ansi_color)


def build_argument_parser(psr):
    psr.add_argument('queryword', action='store', nargs='*', 
            help="""query words. put double quote(") before a word to search the word in string literals.""")
    psr.add_argument('-i', '--ignore-case-query-word', action='append')
    psr.add_argument('-c', '--call-tree', action='store', 
            help="call-tree file. (default '%s')" % _c.default_calltree_path,
            default=_c.default_calltree_path)
    psr.add_argument('-n', '--node-summary', action='store', 
            help="summary file. (default '%s')" % _c.default_summary_path,
            default=_c.default_summary_path)
    psr.add_argument('-o', '--output', action='store', default=STDOUT)
    psr.add_argument('-l', '--line-number-table', action='store', 
            help="line-number table file. (default '%s')" % _c.default_linenumbertable_path,
            default=None)
    psr.add_argument('-d', '--max-depth', action='store', type=int, 
            help="max depth of subtree. -1 for unlimited depth. (default '%d')" % _c.default_max_depth_of_subtree,
            default=_c.default_max_depth_of_subtree)
    psr.add_argument('-f', '--output-form', choices=('callnode', 'treecut', 'path'), 
            default='treecut')
    color_choices=('always', 'never', 'auto')
    psr.add_argument('--color', '--colour', action='store', choices=color_choices, dest='color', 
            help="hilighting with ANSI color.",
            default='auto')
    psr.add_argument('-F', '--fully-qualified-package-name', action='store_true', default=False)
    psr.add_argument("--progress", action='store_true',
            help="show progress to stderr",
            default=False)


def main(argv):
    psr = argparse.ArgumentParser(prog=argv[0], description='agoat keyword search')
    build_argument_parser(psr)

    args = psr.parse_args(argv[1:])
    line_number_table = None
    if args.line_number_table is not None:
        line_number_table = args.line_number_table
    else:
        if os.path.exists(_c.default_linenumbertable_path) or os.path.exists(_c.default_linenumbertable_path + ".gz"):
            line_number_table = _c.default_linenumbertable_path
    ansi_color = sys.stdout.isatty() if args.color == 'auto' else args.color == 'always'
    if ansi_color:
        init_ansi_color()
    if not args.ignore_case_query_word: 
        ignore_case_query_words = []
    else:
        ignore_case_query_words = args.ignore_case_query_word
    if not args.queryword and not ignore_case_query_words:
        sys.exit("no query keyword given")
    do_search(args.call_tree, args.node_summary, args.queryword, ignore_case_query_words, args.output,  line_number_table,
            max_depth=args.max_depth, output_form=args.output_form,
            fully_qualified_package_name=args.fully_qualified_package_name, ansi_color=ansi_color,
            show_progress=args.progress)
