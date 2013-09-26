#!/usr/bin/env python
#coding: utf-8

import argparse
import os
import sys
import pickle

from _utilities import open_w_default
import progress_bar

import _config as _c
import jimp_parser as jp
import jimp_code_term_extractor as jcte
import calltree_builder as cb
import calltree_summarizer as cs
import src_linenumber_converter as slc
from _calltree_data_formatter import format_clzmsig
from _calltree_data_formatter import DATATAG_CALL_TREES, DATATAG_NODE_SUMMARY, DATATAG_LINENUMBER_TABLE
from _calltree_data_formatter import pretty_print_raw_data
import summary


def pretty_print_raw_data_file(data_file, out=sys.stdout):
    with open_w_default(data_file, "rb", sys.stdin) as inp:
        data = pickle.load(inp)
    pretty_print_raw_data(data, out)


def list_entry_points(soot_dir, output_file, option_method_sig=False):
    class_table = dict((clz, cd) \
            for clz, cd in jp.read_class_table_from_dir_iter(soot_dir))
    entry_points = cb.find_entry_points(class_table)

    with open_w_default(output_file, "wb", sys.stdout) as out:
        for ep in sorted(entry_points):
            if not option_method_sig:
                out.write("%s\n" % jp.clzmsig_clz(ep))
            else:
                out.write("%s\n" % format_clzmsig(ep))


def list_methods(soot_dir, output_file):
    class_table = dict((clz, cd) \
            for clz, cd in jp.read_class_table_from_dir_iter(soot_dir))
    sumry = jcte.extract_defined_methods_table(class_table)
    with open_w_default(output_file, "wb", sys.stdout) as out:
        for callee in sumry.callees:
            out.write("%s\n" % format_clzmsig(callee))


def list_literals(soot_dir, output_file):
    class_table = dict((clz, cd) \
            for clz, cd in jp.read_class_table_from_dir_iter(soot_dir))
    sb = summary.SummaryBuilder()
    for clz, cd in class_table.iteritems():
        for md in cd.methods.itervalues():
            sb.append_summary(jcte.extract_referred_literals(md.code, md, cd))
    literals = sb.to_summary().literals

    with open_w_default(output_file, "wb", sys.stdout) as out:
        for lit in literals:
            out.write("%s\n" % lit)


def list_entry_points_from_calltrees(call_tree_file, output_file, option_method_sig=False):
    with open_w_default(call_tree_file, "rb", sys.stdin) as inp:
        # data = pickle.load(inp)  # very very slow in pypy
        data = pickle.loads(inp.read())
    call_trees = data[DATATAG_CALL_TREES]
    del data
    entry_points = cs.extract_entry_points(call_trees)
    del call_trees

    with open_w_default(output_file, "wb", sys.stdout) as out:
        for ep in sorted(entry_points):
            if not option_method_sig:
                out.write("%s\n" % jp.clzmsig_clz(ep))
            else:
                out.write("%s\n" % format_clzmsig(ep))


def list_methods_from_calltrees(call_tree_file, output_file):
    with open_w_default(call_tree_file, "rb", sys.stdin) as inp:
        # data = pickle.load(inp)  # very very slow in pypy
        data = pickle.loads(inp.read())
    call_trees = data[DATATAG_CALL_TREES]
    summary_table = data[DATATAG_NODE_SUMMARY]
    del data

    entry_points = cs.extract_entry_points(call_trees)
    del call_trees

    tot_sumry = summary.Summary()
    for ep in entry_points:
        ep_with_possible_recursive_cxts = [(ep, None), (ep, ep)]
        for ep_w_rc in ep_with_possible_recursive_cxts:
            sumry = summary_table.get(ep_w_rc)
            if sumry:
                sumry.literals = ()
                tot_sumry = tot_sumry + sumry
    callees = tot_sumry.callees

    with open_w_default(output_file, "wb", sys.stdout) as out:
        for callee in callees:
            out.write("%s\n" % format_clzmsig(callee))


def list_literals_from_calltrees(call_tree_file, output_file):
    with open_w_default(call_tree_file, "rb", sys.stdin) as inp:
        # data = pickle.load(inp)  # very very slow in pypy
        data = pickle.loads(inp.read())
    call_trees = data[DATATAG_CALL_TREES]
    summary_table = data[DATATAG_NODE_SUMMARY]
    del data

    entry_points = cs.extract_entry_points(call_trees)
    del call_trees

    tot_sumry = summary.Summary()
    for ep in entry_points:
        ep_with_possible_recursive_cxts = [(ep, None), (ep, ep)]
        for ep_w_rc in ep_with_possible_recursive_cxts:
            sumry = summary_table.get(ep_w_rc)
            if sumry:
                sumry.callees = ()
                tot_sumry = tot_sumry + sumry
    literals = tot_sumry.literals

    with open_w_default(output_file, "wb", sys.stdout) as out:
        for lit in literals:
            out.write("%s\n" % lit)


def generate_call_tree_and_node_summary(entry_point_classes, soot_dir, output_file, show_progress=False):
    log = sys.stderr.write if show_progress else None

    log and log("> building and-or call tree\n")
    class_table = dict((clz, cd) \
            for clz, cd in jp.read_class_table_from_dir_iter(soot_dir))
    entry_points = cb.find_entry_points(class_table, target_class_names=entry_point_classes)

    class_table = cb.inss_to_tree_in_class_table(class_table)
    call_trees = cb.extract_call_andor_trees(class_table, entry_points)

    if show_progress:
        log and log("> extracting summary from each node\n")
        label_set = cs.extract_callnode_labels_in_calltrees(call_trees)
        with progress_bar.drawer(len(label_set)) as rep:
            done_labels = [0]
            def p(label):
                done_labels[0] += 1
                rep(done_labels[0])
            node_summary_table = cs.extract_node_summary_table(call_trees, progress=p)
    else:
        node_summary_table = cs.extract_node_summary_table(call_trees)

    log and log("> saving call tree and summary table\n")
    with open_w_default(output_file, "wb", sys.stdout) as out:
        pickle.dump({DATATAG_CALL_TREES: call_trees, DATATAG_NODE_SUMMARY: node_summary_table}, out,
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
    NotGiven = object()

    psr = argparse.ArgumentParser(description='agoat CLI indexer')
    psr.add_argument('--version', action='version', version='%(prog)s ' + _c.VERSION)
    subpsrs = psr.add_subparsers(dest='command', help='commands')

    psr_index = subpsrs.add_parser('index', help='generate all index data (= gc + gl)')
    psr_index.add_argument('-s', '--soot-dir', action='store', help='soot directory', default=_c.default_soot_dir_path)
    psr_index.add_argument('-j', '--javap-dir', action='store', default=_c.default_javap_dir_path)
    psr_index.add_argument("--progress", action='store_true',
        help="show progress to standard output",
        default=False)

    psr_ep = subpsrs.add_parser('le', help='listing entry points')
    g = psr_ep.add_mutually_exclusive_group()
    g.add_argument('-s', '--soot-dir', action='store', nargs='?', help='soot directory', default=NotGiven)
    g.add_argument('-c', '--call-tree', action='store', nargs='?', help='call-tree file', default=NotGiven)
    psr_ep.add_argument('-o', '--output', action='store', default='-')
    psr_ep.add_argument('-m', '--method-sig', action='store_true', help="output method signatures")

    psr_mt = subpsrs.add_parser('lm', help='listing methods defined within the target code')
    g = psr_mt.add_mutually_exclusive_group()
    g.add_argument('-s', '--soot-dir', action='store', nargs='?', help='soot directory', default=NotGiven)
    g.add_argument('-c', '--call-tree', action='store', nargs='?', help='call-tree file', default=NotGiven)
    psr_mt.add_argument('-o', '--output', action='store', default='-')

    psr_lt = subpsrs.add_parser('ll', help='listing literals')
    g = psr_lt.add_mutually_exclusive_group()
    g.add_argument('-s', '--soot-dir', action='store', nargs='?', help='soot directory', default=NotGiven)
    g.add_argument('-c', '--call-tree', action='store', nargs='?', help='call-tree file', default=NotGiven)
    psr_lt.add_argument('-o', '--output', action='store', default='-')

    psr_sl = subpsrs.add_parser('gl', help='generate line number table')
    psr_sl.add_argument('-s', '--soot-dir', action='store', help='soot directory', default=_c.default_soot_dir_path)
    psr_sl.add_argument('-j', '--javap-dir', action='store', default=_c.default_javap_dir_path)
    psr_sl.add_argument('-o', '--output', action='store',
            help="output file. (default '%s')" % _c.default_linenumbertable_path,
            default=_c.default_linenumbertable_path)

    psr_ct = subpsrs.add_parser('gc', help='generate call tree and node summary table')
    psr_ct.add_argument('-e', '--entry-point', action='store', nargs='*', dest='entrypointclasses',
            help='entry-point class. If not given, all possible classes will be regarded as entry points')
    psr_ct.add_argument('-s', '--soot-dir', action='store', help='soot directory', default=_c.default_soot_dir_path)
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
        if args.soot_dir is not NotGiven:
            soot_dir = _c.default_soot_dir_path if args.soot_dir is None else args.soot_dir
            list_entry_points(soot_dir, args.output, args.method_sig)
        elif args.call_tree is not NotGiven:
            call_tree_file= _c.default_calltree_path if args.call_tree is None else args.call_tree
            list_entry_points_from_calltrees(call_tree_file, args.output, args.method_sig)
        else:
            sys.exit("need either -s or -c")
    elif args.command == 'lm':
        if args.soot_dir is not NotGiven:
            soot_dir = _c.default_soot_dir_path if args.soot_dir is None else args.soot_dir
            list_methods(soot_dir, args.output)
        elif args.call_tree is not NotGiven:
            call_tree_file= _c.default_calltree_path if args.call_tree is None else args.call_tree
            list_methods_from_calltrees(call_tree_file, args.output)
        else:
            sys.exit("need either -s or -c")
    elif args.command == 'll':
        if args.soot_dir is not NotGiven:
            soot_dir = _c.default_soot_dir_path if args.soot_dir is None else args.soot_dir
            list_literals(soot_dir, args.output)
        elif args.call_tree is not NotGiven:
            call_tree_file= _c.default_calltree_path if args.call_tree is None else args.call_tree
            list_literals_from_calltrees(call_tree_file, args.output)
        else:
            sys.exit("need either -s or -c")
    elif args.command == 'gl':
        generate_linenumber_table(args.soot_dir, args.javap_dir, args.output)
    elif args.command == 'gc':
        generate_call_tree_and_node_summary(args.entrypointclasses, args.soot_dir, args.output,
            show_progress=args.progress)
    elif args.command == "index":
        if args.progress:
            sys.stderr.write("> generating/saving line number table\n")
        generate_linenumber_table(args.soot_dir, args.javap_dir, _c.default_linenumbertable_path)
        generate_call_tree_and_node_summary(None, args.soot_dir, _c.default_calltree_path,
            show_progress=args.progress)
    elif args.command == 'debug':
        if args.pretty_print:
            pretty_print_raw_data_file(args.pretty_print)
    else:
        assert False


if __name__ == '__main__':
    main(sys.argv)