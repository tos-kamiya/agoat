#coding: utf-8

import os
import sys
import argparse
import pickle
import pprint

from _utilities import open_w_default

import jimp_parser as jp
import jimp_code_term_extractor as jcte
import calltree_builder as cb
import node_summarizer as ns
import calltree_query as cq


def list_entry_points(soot_dir, output_file):
    class_table = dict((clz, cd) \
            for clz, cd in jp.read_class_table_from_dir_iter(soot_dir))
    entry_points = cb.find_entry_points(class_table)

    with open_w_default(output_file, "wb", sys.stdout) as out:
        for ep in sorted(entry_points):
            out.write("%s\n" % ep[0])


def list_methods(soot_dir, output_file):
    class_table = dict((clz, cd) \
            for clz, cd in jp.read_class_table_from_dir_iter(soot_dir))
    methods = jcte.extract_methods(class_table)

    with open_w_default(output_file, "wb", sys.stdout) as out:
        for clz, msig in methods:
            out.write("%s\t%s\n" % (clz, msig))


def generate_call_tree_and_node_summary(entry_points, soot_dir, output_file, pretty_print=False):
    class_table = dict((clz, cd) \
            for clz, cd in jp.read_class_table_from_dir_iter(soot_dir))

    if entry_points is None:
        entry_points = cb.find_entry_points(class_table)

    class_table = cb.inss_to_tree_in_class_table(class_table)
    call_trees = cb.extract_call_andor_trees(class_table, entry_points)
    node_summary_table = {}
    for call_tree in call_trees:
        node_summary_table = ns.extract_node_summerize_table(call_tree, summary_memo=node_summary_table)

    with open_w_default(output_file, "wb", sys.stdout) as out:
        if pretty_print:
            pp = pprint.PrettyPrinter(indent=4, stream=out)
            for call_tree in call_trees:
                out.write("call tree:\n")
                pp.pprint(call_tree)
            out.write("node summary table:\n")
            pp.pprint(node_summary_table)
        else:
            pickle.dump((call_trees, node_summary_table), out)


def search_method_bodies(call_tree_file, query_words, output_file, ignore_case=False):
    with open_w_default(call_tree_file, "rb", sys.stdin) as inp:
        call_trees, node_summary_table = pickle.load(inp)

    query_patterns = cq.build_query_pattern_list(query_words, ignore_case=ignore_case)
    call_nodes = cq.find_lower_call_nodes(query_patterns, call_trees, node_summary_table)

    with open_w_default(output_file, "wb", sys.stdout) as out:
        pp = pprint.PrettyPrinter(indent=4, stream=out)
        for call_node in sorted(call_nodes):
            out.write("---\n")
            recursive_context = call_node[1]
            invoked = call_node[2]
            clz, msig = invoked[1], invoked[2]
            out.write("%s\t%s\t%s\n" % (clz, msig, recursive_context))
            marked = cq.mark_uncontributing_nodes_w_call(query_patterns, call_node)
            pp.pprint(marked)


def main(argv):
    default_calltree_path = os.path.join(os.curdir, 'agoat.calltree')

    psr = argparse.ArgumentParser(description='agoat command-line')
    subpsrs = psr.add_subparsers(dest='command', help='commands')

    psr_ep = subpsrs.add_parser('e', help='listing entry point classes')
    psr_ep.add_argument('-s', '--soot-dir', action='store', help='soot directory', default='sootOutput')
    psr_ep.add_argument('-o', '--output', action='store', help="output file. '-' for standard output", default='-')

    psr_mt = subpsrs.add_parser('m', help='listing methods (defined methods and used ones)')
    psr_mt.add_argument('-s', '--soot-dir', action='store', help='soot directory', default='sootOutput')
    psr_mt.add_argument('-o', '--output', action='store', help="output file. '-' for standard output", default='-')

    psr_ct = subpsrs.add_parser('c', help='generate call tree and node summary table')
    psr_ct.add_argument('-e', '--entry-point', action='store', nargs='*', dest='entrypointclasses',
            help='entry-point class. If not given, all possible classes will be regarded as entry points')
    psr_ct.add_argument('-s', '--soot-dir', action='store', help='soot directory', default='sootOutput')
    psr_ct.add_argument('-o', '--output', action='store', 
            help="output file. '-' for standard output. (default '%s')" % default_calltree_path, 
            default=default_calltree_path)
    psr_ct.add_argument('-p', '--pretty-print', action='store_true', help='print call-tree in human-readable format')

    psr_q = subpsrs.add_parser('q', help='search query words in call tree')
    psr_q.add_argument('-c', '--call-tree', action='store', 
           help="call-tree file. '-' for standard input. (default '%s')" % default_calltree_path,
            default=default_calltree_path)
    psr_q.add_argument('queryword', action='store', nargs='+', help="query words")
    psr_q.add_argument('-I', '--ignore-case', action='store_true')
    psr_q.add_argument('-o', '--output', action='store', help="output file. '-' for standard output", default='-')

    args = psr.parse_args(argv[1:])
    if args.command == 'm':
        list_methods(args.soot_dir, args.output, args.entry_point)
    elif args.command == 'c':
        if args.entrypointclasses is not None:
            eps = []
            entry_point_msig = jp.MethodSig(None, "main", ("java.lang.String[]",))
            for c in args.entrypointclasses:
                entry_point = (c, entry_point_msig)
                eps.append(entry_point)
        else:
            eps = None
        generate_call_tree_and_node_summary(eps, args.soot_dir, args.output, args.pretty_print)
    elif args.command == 'q':
        search_method_bodies(args.call_tree, args.queryword, args.output, args.ignore_case)
    else:
        assert False


if __name__ == '__main__':
    main(sys.argv)

