#!/usr/bin/env python
#coding: utf-8

import argparse
import os
import sys
import pickle
import itertools

from _utilities import open_w_default
import progress_bar

import _config as _c
import jimp_parser as jp
import jimp_code_term_extractor as jcte
import calltree_builder as cb
import calltree_sammarizer as cs
import src_linenumber_converter as slc
from _calltree_data_formatter import format_clz_msig, format_msig
from _calltree_data_formatter import DATATAG_CALL_TREES, DATATAG_NODE_SAMMARY, DATATAG_LINENUMBER_TABLE
from _calltree_data_formatter import pretty_print_pickle_data
import sammary


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
    sam = jcte.extract_defined_methods_table(class_table)
    methods = list(sam.invokeds)

    with open_w_default(output_file, "wb", sys.stdout) as out:
        for clz, msig in methods:
            out.write("%s\n" % format_clz_msig(clz, msig))


def list_literals(soot_dir, output_file):
    class_table = dict((clz, cd) \
            for clz, cd in jp.read_class_table_from_dir_iter(soot_dir))
    sb = sammary.SammaryBuilder()
    for clz, cd in class_table.iteritems():
        for msig, md in cd.methods.iteritems():
            sb.append_sammary(jcte.extract_referred_literals(md.code, md, cd))
    literals = sb.to_sammary().literals

    with open_w_default(output_file, "wb", sys.stdout) as out:
        for lit in literals:
            out.write("%s\n" % lit)


def generate_call_tree_and_node_sammary(entry_point_classes, soot_dir, output_file, 
        trace_invocation_via_interface=True, show_progress=False):
    log = sys.stderr.write if show_progress else None

    log and log("> reading code of classes\n")
    class_table = dict((clz, cd) \
            for clz, cd in jp.read_class_table_from_dir_iter(soot_dir, trace_invocation_via_interface))
    entry_points = cb.find_entry_points(class_table, target_class_names=entry_point_classes)

    log and log("> building and-or call tree\n")
    class_table = cb.inss_to_tree_in_class_table(class_table)
    call_trees = cb.extract_call_andor_trees(class_table, entry_points)

    if show_progress:
        log and log("> extracting sammary from each node\n")
        invoked_set = cs.extract_callnode_invokeds_in_calltrees(call_trees)
        with progress_bar.drawer(len(invoked_set)) as rep:
            done_invokeds = [0]
            def p(invoked):
                done_invokeds[0] += 1
                rep(done_invokeds[0])
            node_sammary_table = cs.extract_node_sammary_table(call_trees, progress=p)
    else:
        node_sammary_table = cs.extract_node_sammary_table(call_trees)

    log and log("> saving index data\n")
    with open_w_default(output_file, "wb", sys.stdout) as out:
        pickle.dump({DATATAG_CALL_TREES: call_trees, DATATAG_NODE_SAMMARY: node_sammary_table}, out,
                protocol=1)


def generate_linenumber_table(soot_dir, javap_dir, output_file):
    assert os.path.isdir(soot_dir)
    assert os.path.isdir(javap_dir)

    class_table = dict((clz, cd) \
            for clz, cd in jp.read_class_table_from_dir_iter(soot_dir))
    claz_msig2invocationindex2linenum = slc.make_invocationindex_to_src_linenum_table(javap_dir)
    clz_msig2conversion = slc.jimp_linnum_to_src_linenum_table(class_table, claz_msig2invocationindex2linenum)

    with open_w_default(output_file, "wb", sys.stdout) as out:
        pickle.dump({DATATAG_LINENUMBER_TABLE: clz_msig2conversion}, out,
                protocol=1)


def main(argv):
    psr = argparse.ArgumentParser(description='agoat CLI indexer')
    psr.add_argument('--version', action='version', version='%(prog)s ' + _c.VERSION)
    subpsrs = psr.add_subparsers(dest='command', help='commands')

    psr_ep = subpsrs.add_parser('le', help='listing entry point classes')
    psr_ep.add_argument('-s', '--soot-dir', action='store', help='soot directory', default='sootOutput')
    psr_ep.add_argument('-o', '--output', action='store', default='-')
    psr_ep.add_argument('-m', '--method-sig', action='store_true', help="output method signatures")

    psr_mt = subpsrs.add_parser('lm', help='listing methods defined within the target code')
    psr_mt.add_argument('-s', '--soot-dir', action='store', help='soot directory', default='sootOutput')
    psr_mt.add_argument('-o', '--output', action='store', default='-')

    psr_mt = subpsrs.add_parser('ll', help='listing literals')
    psr_mt.add_argument('-s', '--soot-dir', action='store', help='soot directory', default='sootOutput')
    psr_mt.add_argument('-o', '--output', action='store', default='-')

    psr_sl = subpsrs.add_parser('gl', help='generate line number table')
    psr_sl.add_argument('-s', '--soot-dir', action='store', help='soot directory', default='sootOutput')
    psr_sl.add_argument('-j', '--javap-dir', action='store', default=_c.default_javap_dir_path)
    psr_sl.add_argument('-o', '--output', action='store', 
            help="output file. (default '%s')" % _c.default_linenumbertable_path, 
            default=_c.default_linenumbertable_path)

    psr_ct = subpsrs.add_parser('gc', help='generate call tree and node sammary table')
    psr_ct.add_argument('-e', '--entry-point', action='store', nargs='*', dest='entrypointclasses',
            help='entry-point class. If not given, all possible classes will be regarded as entry points')
    psr_ct.add_argument('-s', '--soot-dir', action='store', help='soot directory', default='sootOutput')
    psr_ct.add_argument('-I', '--ignore-method-invocation-via-interface', action='store_true',
            default=False)
    psr_ct.add_argument('-o', '--output', action='store', 
            help="output file. (default '%s')" % _c.default_calltree_path, 
            default=_c.default_calltree_path)
    psr_ct.add_argument("--progress", action='store_true',
            help="show progress to standard output",
            default=False)

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
        generate_call_tree_and_node_sammary(args.entrypointclasses, args.soot_dir, args.output, 
            trace_invocation_via_interface=not args.ignore_method_invocation_via_interface,
            show_progress=args.progress)
    elif args.command == 'debug':
        if args.pretty_print:
            pretty_print_pickle_data_file(args.pretty_print)
    else:
        assert False


if __name__ == '__main__':
    main(sys.argv)