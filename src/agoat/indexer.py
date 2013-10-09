#coding: utf-8

import argparse
import gzip
import os
import sys
import pickle

from _utilities import STDIN, STDOUT, open_gziped_file_when_available

from . import _config as _c
from . import jimp_parser as jp
from . import calltree_builder as cb
from . import calltree_summary as cs
from . import src_linenumber_converter as slc
from ._calltree_data_formatter import DATATAG_ENTRY_POINTS, DATATAG_CALL_TREES, DATATAG_NODE_SUMMARY, DATATAG_LINENUMBER_TABLE


def generate_call_trees(entry_point_classes, soot_dir, output_file):
    class_table = dict((clz, cd) \
            for clz, cd in jp.read_class_table_from_dir_iter(soot_dir))
    entry_points = cb.find_entry_points(class_table, target_class_names=entry_point_classes)

    class_table = cb.inss_to_tree_in_class_table(class_table)
    call_trees = cb.extract_call_andor_trees(class_table, entry_points)

    with gzip.open(output_file + ".gz", "wb") as out:
        pickle.dump({DATATAG_CALL_TREES: call_trees, DATATAG_ENTRY_POINTS: entry_points}, out,
                protocol=1)
    return entry_points, call_trees


def generate_node_summary(call_tree_file, output_file, call_trees_data=None):
    if call_trees_data is not None:
        entry_points, call_trees = call_trees_data
    else:
        with open_gziped_file_when_available(call_tree_file, "rb") as inp:
            # data = pickle.load(inp)  # very very slow in pypy
            data = pickle.loads(inp.read())
        entry_points = data[DATATAG_ENTRY_POINTS]
        call_trees = data[DATATAG_CALL_TREES]

    node_summary_table = cs.extract_node_summary_table(call_trees)

    with gzip.open(output_file + ".gz", "wb") as out:
        pickle.dump({DATATAG_NODE_SUMMARY: node_summary_table, DATATAG_ENTRY_POINTS: entry_points}, out,
                protocol=1)


def generate_linenumber_table(soot_dir, javap_dir, output_file):
    assert os.path.isdir(soot_dir)
    assert os.path.isdir(javap_dir)

    class_table = dict((clz, cd) \
            for clz, cd in jp.read_class_table_from_dir_iter(soot_dir))
    claz_msig2invocationindex2linenum = slc.make_invocationindex_to_src_linenum_table(javap_dir)
    clz_msig2conversion = slc.jimp_linnum_to_src_linenum_table(class_table, claz_msig2invocationindex2linenum)

    with gzip.open(output_file + ".gz", "wb") as out:
        pickle.dump({DATATAG_LINENUMBER_TABLE: clz_msig2conversion}, out,
                protocol=1)


def main(argv):
    psr = argparse.ArgumentParser(prog=argv[0], description='agoat indexer')
    subpsrs = psr.add_subparsers(dest='command', help='commands')

    psr_index = subpsrs.add_parser('all', help='generate all index data (= linenumber + calltree + nodesummary)')
    psr_index.add_argument('-s', '--soot-dir', action='store', help='soot directory', default=_c.default_soot_dir_path)
    psr_index.add_argument('-j', '--javap-dir', action='store', default=_c.default_javap_dir_path)
    psr_index.add_argument("--progress", action='store_true',
            help="show progress to standard output",
            default=False)

    psr_sl = subpsrs.add_parser('linenumber', help='generate line number table')
    psr_sl.add_argument('-s', '--soot-dir', action='store', help='soot directory', default=_c.default_soot_dir_path)
    psr_sl.add_argument('-j', '--javap-dir', action='store', default=_c.default_javap_dir_path)
    psr_sl.add_argument('-o', '--output', action='store',
            help="output file. (default '%s')" % _c.default_linenumbertable_path,
            default=_c.default_linenumbertable_path)

    psr_ct = subpsrs.add_parser('calltree', help='generate call tree')
    psr_ct.add_argument('-e', '--entry-point', action='store', nargs='*', dest='entrypointclasses',
            help='entry-point class. If not given, all possible classes will be regarded as entry points')
    psr_ct.add_argument('-s', '--soot-dir', action='store', help='soot directory', default=_c.default_soot_dir_path)
    psr_ct.add_argument('-o', '--output', action='store',
            help="output file. (default '%s')" % _c.default_calltree_path,
            default=_c.default_calltree_path)

    psr_gs = subpsrs.add_parser('nodesummary', help='generate node summary table')
    psr_gs.add_argument('-c', '--call-tree', action='store', help='call-tree file', default=_c.default_calltree_path)
    psr_gs.add_argument('-o', '--output', action='store',
            help="output file. (default '%s')" % _c.default_summary_path,
            default=_c.default_summary_path)

    args = psr.parse_args(argv[1:])
    if args.command == 'linenumber':
        generate_linenumber_table(args.soot_dir, args.javap_dir, args.output)
    elif args.command == 'calltree':
        generate_call_trees(args.entrypointclasses, args.soot_dir, args.output)
    elif args.command == 'nodesummary':
        generate_node_summary(args.call_tree, args.output)
    elif args.command == "all":
        if args.progress:
            sys.stderr.write("> generating/saving line number table\n")
        generate_linenumber_table(args.soot_dir, args.javap_dir, _c.default_linenumbertable_path)
        if args.progress:
            sys.stderr.write("> generating/saving call trees\n")
        call_trees_data = generate_call_trees(None, args.soot_dir, _c.default_calltree_path)
        if args.progress:
            sys.stderr.write("> generating/saving summary table\n")
        generate_node_summary(_c.default_calltree_path, _c.default_summary_path,
                call_trees_data=call_trees_data)
    else:
        assert False
