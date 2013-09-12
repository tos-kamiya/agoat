#coding: utf-8

import argparse
import os
import sys
import pickle

from _utilities import open_w_default, sort_uniq

import jimp_parser as jp
import jimp_code_term_extractor as jcte
import calltree as ct
import calltree_builder as cb
import calltree_summarizer as cs
import calltree_query as cq
import src_linenumber_converter as slc
from _calltree_data_formatter import format_clz, format_msig, format_clz_msig
from _calltree_data_formatter import DATATAG_CALL_TREES, DATATAG_NODE_SUMMARY, DATATAG_LINENUMBER_TABLE
from _calltree_data_formatter import pretty_print_pickle_data, format_call_tree_node_compact, init_ansi_color


VERSION = "0.5.0"


def pretty_print_pickle_data_file(data_file, out=sys.stdout):
    with open_w_default(data_file, "rb", sys.stdin) as inp:
        data = pickle.load(inp)
    pretty_print_pickle_data(data, out)


def list_entry_points(soot_dir, output_file, option_method_sig=False):
    class_table = dict((clz, cd) \
            for clz, cd in jp.read_class_table_from_dir_iter(soot_dir))
    entry_points = cb.find_entry_points(class_table)

    with open_w_default(output_file, "wb", sys.stdout) as out:
        for ep in sorted(entry_points):
            if not option_method_sig:
                out.write("%s\n" % ep[0])
            else:
                out.write("%s\n" % format_clz_msig(*ep))

def list_methods(soot_dir, output_file):
    class_table = dict((clz, cd) \
            for clz, cd in jp.read_class_table_from_dir_iter(soot_dir))
    methods = jcte.extract_methods(class_table)

    with open_w_default(output_file, "wb", sys.stdout) as out:
        for clz, msig in methods:
            out.write("%s\n" % format_clz_msig(clz, msig))


def list_literals(soot_dir, output_file):
    class_table = dict((clz, cd) \
            for clz, cd in jp.read_class_table_from_dir_iter(soot_dir))
    literals = set()
    for clz, cd in class_table.iteritems():
        for msig, md in cd.methods.iteritems():
            literals.update(jcte.extract_referred_literals(md.code, md, cd))
    literals = sorted(literals)

    with open_w_default(output_file, "wb", sys.stdout) as out:
        for lit in literals:
            out.write("%s\n" % lit)


def generate_call_tree_and_node_summary(entry_point_classes, soot_dir, output_file):
    class_table = dict((clz, cd) \
            for clz, cd in jp.read_class_table_from_dir_iter(soot_dir))

    entry_points = cb.find_entry_points(class_table, target_class_names=entry_point_classes)

    class_table = cb.inss_to_tree_in_class_table(class_table)
    call_trees = cb.extract_call_andor_trees(class_table, entry_points)
    node_summary_table = cs.extract_node_summary_table(call_trees)

    with open_w_default(output_file, "wb", sys.stdout) as out:
        pickle.dump({DATATAG_CALL_TREES: call_trees, DATATAG_NODE_SUMMARY: node_summary_table}, out)


def generate_linenumber_table(soot_dir, javap_dir, output_file):
    assert os.path.isdir(soot_dir)
    assert os.path.isdir(javap_dir)

    class_table = dict((clz, cd) \
            for clz, cd in jp.read_class_table_from_dir_iter(soot_dir))
    claz_msig2invocationindex2linenum = slc.make_invocationindex_to_src_linenum_table(javap_dir)
    clz_msig2conversion = slc.jimp_linnum_to_src_linenum_table(class_table, claz_msig2invocationindex2linenum)

    with open_w_default(output_file, "wb", sys.stdout) as out:
        pickle.dump({DATATAG_LINENUMBER_TABLE: clz_msig2conversion}, out)


def extract_node_contribution(call_node, query_patterns):
    node_id_to_cont = {}
    cont_clzs = set()
    cont_msigs = set()
    cont_literals = set()

    def update_about_invoked(invoked):
        clz, msig, literals = invoked[1], invoked[2], invoked[3]
        clz_cont = clz in cont_clzs or len(cq.missing_query_patterns([(clz, '')], query_patterns)) < len_query_patterns
        clz_cont and cont_clzs.add(clz)
        msig_cont = msig in cont_msigs or len(cq.missing_query_patterns([('', msig)], query_patterns)) < len_query_patterns
        msig_cont and cont_msigs.add(msig)
        literal_cont = (not not literals) and len(cq.missing_query_patterns(literals, query_patterns)) < len_query_patterns
        literal_cont and cont_literals.add(literals)
        return clz_cont, msig_cont, literal_cont

    len_query_patterns = len(query_patterns)
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


def search_method_bodies(call_tree_file, query_words, output_file, ignore_case=False, line_number_table=None, 
        max_depth=-1, fully_qualified_package_name=False, ansi_color=False):
    with open_w_default(call_tree_file, "rb", sys.stdin) as inp:
        data = pickle.load(inp)
    call_trees = data[DATATAG_CALL_TREES]
    node_summary_table = data[DATATAG_NODE_SUMMARY]
    del data

    clz_msig2conversion = None
    if line_number_table is not None:
        with open_w_default(line_number_table, "rb", sys.stdin) as inp:
            data = pickle.load(inp)
            clz_msig2conversion = data[DATATAG_LINENUMBER_TABLE]
        del data

    query_patterns = cq.build_query_pattern_list(query_words, ignore_case=ignore_case)

    pred = cq.make_callnode_fullfill_query_predicate_w_memo(query_patterns, node_summary_table)
    call_nodes = cq.get_lower_bound_call_nodes(call_trees, pred)

    pred = cq.make_treecut_fullfill_query_predicate(query_patterns)
    shallowers = filter(None, (cq.extract_shallowest_treecut(call_node, pred, max_depth) for call_node in call_nodes))
    if call_nodes and not shallowers:
        sys.stderr.write("> warning: All found results are filtered out by limitation of max call-tree depth (option -D).\n")

    contextlesses = [remove_outermost_loc_info(remove_recursive_contexts(cn)) for cn in shallowers]
    call_node_wo_rcs = sort_uniq(contextlesses, key=cb.callnode_label)

    markeds = []
    node_id_to_cont = {}
    cont_clzs = set()
    cont_msigs = set()
    cont_literals = set()
    contribution_data = (node_id_to_cont, cont_clzs, cont_msigs, cont_literals)
    for cn in call_node_wo_rcs:
        ni2c, cc, cm, cl = extract_node_contribution(cn, query_patterns)
        if ni2c[id(cn)]:
            markeds.append(cn)
            node_id_to_cont.update(ni2c.iteritems())
            cont_clzs.update(cc)
            cont_msigs.update(cm)
            cont_literals.update(cl)

    with open_w_default(output_file, "wb", sys.stdout) as out:
        for cn in markeds:
            out.write("---\n")
            format_call_tree_node_compact(cn, out, contribution_data, clz_msig2conversion=clz_msig2conversion,
                    fully_qualified_package_name=fully_qualified_package_name, ansi_color=ansi_color)
#         pp = pprint.PrettyPrinter(indent=4, stream=out)
#         for call_node in sorted(call_nodes):
#             out.write("---\n")
#             recursive_context = call_node[1]
#             invoked = call_node[2]
#             clz, msig = invoked[1], invoked[2]
#             out.write("%s\t%s\t%s\n" % (clz, msig, recursive_context))
#             marked = cq.mark_uncontributing_nodes_w_call(call_node, query_patterns)
#             pp.pprint(marked)

def main(argv):
    default_calltree_path = 'agoat.calltree'
    default_linenumbertable_path = 'agoat.linenumbertable'
    default_javap_dir_path = 'javapOutput'
    defalut_max_depth_of_subtree = 5

    psr = argparse.ArgumentParser(description='agoat command-line')
    psr.add_argument('--version', action='version', version='%(prog)s ' + VERSION)
    subpsrs = psr.add_subparsers(dest='command', help='commands')

    psr_ep = subpsrs.add_parser('le', help='listing entry point classes')
    psr_ep.add_argument('-s', '--soot-dir', action='store', help='soot directory', default='sootOutput')
    psr_ep.add_argument('-o', '--output', action='store', help="output file. '-' for standard output", default='-')
    psr_ep.add_argument('-m', '--method-sig', action='store_true', help="output method signatures")

    psr_mt = subpsrs.add_parser('lm', help='listing methods (defined methods and used ones)')
    psr_mt.add_argument('-s', '--soot-dir', action='store', help='soot directory', default='sootOutput')
    psr_mt.add_argument('-o', '--output', action='store', help="output file. '-' for standard output", default='-')

    psr_mt = subpsrs.add_parser('ll', help='listing literals')
    psr_mt.add_argument('-s', '--soot-dir', action='store', help='soot directory', default='sootOutput')
    psr_mt.add_argument('-o', '--output', action='store', help="output file. '-' for standard output", default='-')

    psr_sl = subpsrs.add_parser('gl', help='generate line number table')
    psr_sl.add_argument('-s', '--soot-dir', action='store', help='soot directory', default='sootOutput')
    psr_sl.add_argument('-j', '--javap-dir', action='store', default=default_javap_dir_path)
    psr_sl.add_argument('-o', '--output', action='store', 
            help="output file. '-' for standard output. (default '%s')" % default_linenumbertable_path, 
            default=default_linenumbertable_path)

    psr_ct = subpsrs.add_parser('gc', help='generate call tree and node summary table')
    psr_ct.add_argument('-e', '--entry-point', action='store', nargs='*', dest='entrypointclasses',
            help='entry-point class. If not given, all possible classes will be regarded as entry points')
    psr_ct.add_argument('-s', '--soot-dir', action='store', help='soot directory', default='sootOutput')
    psr_ct.add_argument('-o', '--output', action='store', 
            help="output file. '-' for standard output. (default '%s')" % default_calltree_path, 
            default=default_calltree_path)

    psr_q = subpsrs.add_parser('q', help='search query words in call tree')
    psr_q.add_argument('queryword', action='store', nargs='+', help="query words")
    psr_q.add_argument('-c', '--call-tree', action='store', 
            help="call-tree file. '-' for standard input. (default '%s')" % default_calltree_path,
            default=default_calltree_path)
    psr_q.add_argument('-I', '--ignore-case', action='store_true')
    psr_q.add_argument('-o', '--output', action='store', help="output file. '-' for standard output", default='-')
    psr_q.add_argument('-l', '--line-number-table', action='store', 
            help="line-number table file. '-' for standard input. (default '%s')" % default_linenumbertable_path,
            default=None)
    psr_q.add_argument('-a', '--ansi-color', action='store_true', default=False)
    psr_q.add_argument('-D', '--max-depth', action='store', type=int, 
            help="max depth of subtree. -1 for unlimited depth. (default is '%d')" % defalut_max_depth_of_subtree,
            default=defalut_max_depth_of_subtree)
    psr_q.add_argument('-F', '--fully-qualified-package-name', action='store_true', default=False)

    psr_db = subpsrs.add_parser('debug', help='debug function')
    psr_db.add_argument('-p', '--pretty-print', action='store', help='pretty print internal data')

    args = psr.parse_args(argv[1:])
    if args.command == 'le':
        list_entry_points(args.soot_dir, args.output, args.method_sig)
    elif args.command == 'lm':
        list_methods(args.soot_dir, args.output)
    elif args.command == 'll':
        list_literals(args.soot_dir, args.output)
    elif args.command == 'gl':
        generate_linenumber_table(args.soot_dir, args.javap_dir, args.output)
    elif args.command == 'gc':
        generate_call_tree_and_node_summary(args.entrypointclasses, args.soot_dir, args.output)
    elif args.command == 'q':
        line_number_table = None
        if args.line_number_table is not None:
            line_number_table = args.line_number_table
        else:
            if os.path.exists(default_linenumbertable_path):
                line_number_table = default_linenumbertable_path
        if args.ansi_color:
            init_ansi_color()
        search_method_bodies(args.call_tree, args.queryword, args.output, args.ignore_case, line_number_table, 
                args.max_depth, args.fully_qualified_package_name, args.ansi_color)
    elif args.command == 'debug':
        if args.pretty_print:
            pretty_print_pickle_data_file(args.pretty_print)
    else:
        assert False


if __name__ == '__main__':
    main(sys.argv)