#coding: utf-8

import sys
import argparse
import pickle
import pprint

from _utilities import open_w_default

import jimp_parser as jp
import jimp_code_term_extractor as jcte
import calltree_builder as cb
import node_summarizer as ns

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


def generate_call_tree(entry_point, soot_dir, output_file, pretty_print=False):
    class_table = dict((clz, cd) \
            for clz, cd in jp.read_class_table_from_dir_iter(soot_dir))
    class_table = cb.inss_to_tree_in_class_table(class_table)
    call_tree = cb.extract_call_andor_tree(class_table, entry_point)

    with open_w_default(output_file, "wb", sys.stdout) as out:
        if pretty_print:
            pp = pprint.PrettyPrinter(indent=4, stream=out)
            pp.pprint(call_tree)
        else:
            pickle.dump(call_tree, out)


def generate_node_summary(call_tree_file, output_file, pretty_print=False):
    with open_w_default(call_tree_file, "rb", sys.stdin) as inp:
        call_tree = pickle.load(inp)

    node_summary_table = ns.extract_node_summerize_table(call_tree)

    with open_w_default(output_file, "wb", sys.stdout) as out:
        if pretty_print:
            pp = pprint.PrettyPrinter(indent=4, stream=out)
            pp.pprint(node_summary_table)
        else:
            pickle.dump(node_summary_table, out)


def main(argv):
    # sootOutputからエントリポイント一覧を取得する
    # sootOutputとエントリポイントからコールツリーを作成する
    # コールツリーに対してノードサマリを作成する
    # 検索する

    psr = argparse.ArgumentParser(description='agoat command-line')
    subpsrs = psr.add_subparsers(help='commands', dest='command')

    psr_ep = subpsrs.add_parser('e', help='listing entry points')
    psr_ep.add_argument('-s', '--soot-dir', action='store', help='soot directory', default='sootOutput')
    psr_ep.add_argument('-o', '--output', action='store', help="output file. '-' for standard output", default='-')

    psr_mt = subpsrs.add_parser('m', help='listing methods')
    psr_mt.add_argument('-s', '--soot-dir', action='store', help='soot directory', default='sootOutput')
    psr_mt.add_argument('-o', '--output', action='store', help="output file. '-' for standard output", default='-')

    psr_ct = subpsrs.add_parser('c', help='generate call tree')
    psr_ct.add_argument('entrypoint', action='store', help='entry-point class')
    psr_ct.add_argument('-s', '--soot-dir', action='store', help='soot directory', default='sootOutput')
    psr_ct.add_argument('-o', '--output', action='store', help="output file. '-' for standard output", default='-')
    psr_ct.add_argument('-p', '--pretty-print', action='store_true', help='print call-tree in human-readable format')

    psr_ns = subpsrs.add_parser('n', help='generate node summary')
    psr_ns.add_argument('calltree', action='store', help="call-tree file. '-' for standard input")
    psr_ns.add_argument('-o', '--output', action='store', help="output file. '-' for standard output", default='-')
    psr_ns.add_argument('-p', '--pretty-print', action='store_true', help='print call-tree in human-readable format')

    args = psr.parse_args(argv[1:])
    if args.command == 'e':
        list_entry_points(args.soot_dir, args.output)
    elif args.command == 'm':
        list_methods(args.soot_dir, args.output)
    elif args.command == 'c':
        entry_point_msig = jp.MethodSig(None, "main", ("java.lang.String[]",))
        entry_point = (args.entrypoint, entry_point_msig)
        generate_call_tree(entry_point, args.soot_dir, args.output, args.pretty_print)
    elif args.command == 'n':
        generate_node_summary(args.calltree, args.output, args.pretty_print)
    else:
        assert False

if __name__ == '__main__':
    main(sys.argv)

