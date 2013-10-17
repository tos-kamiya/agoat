#coding: utf-8

import argparse
import os
import sys
import pickle

from _utilities import STDIN, STDOUT, open_gziped_file_when_available

from . import _config as _c
from . import jimp_parser as jp
from . import jimp_code_term_extractor as jcte
from . import calltree_builder as cb
from . import calltree as ct
from . import calltree_summary as cs
from ._calltree_data_formatter import DATATAG_ENTRY_POINTS, DATATAG_NODE_SUMMARY, DATATAG_CALL_TREES
from ._calltree_data_formatter import pretty_print_raw_data


def pretty_print_raw_data_file(data_file, out=sys.stdout):
    with open_gziped_file_when_available(data_file, "rb") as inp:
        # data = pickle.load(inp)  # very very slow in pypy
        data = pickle.loads(inp.read())
    pretty_print_raw_data(data, out)


def list_entry_points(soot_dir, output_file, option_method_sig=False):
    class_table = dict((clz, cd) \
            for clz, cd in jp.read_class_table_from_dir_iter(soot_dir))
    entry_points = cb.find_entry_points(class_table)

    with open(output_file, "wb") as out:
        for ep in sorted(entry_points):
            if not option_method_sig:
                out.write("%s\n" % jp.clzmsig_clz(ep))
            else:
                out.write("%s\n" % jp.format_clzmsig(ep))


def list_methods(soot_dir, output_file):
    class_table = dict((clz, cd) \
            for clz, cd in jp.read_class_table_from_dir_iter(soot_dir))
    sumry = jcte.extract_defined_methods_table(class_table)
    with open(output_file, "wb") as out:
        for callee in sumry.callees:
            out.write("%s\n" % jp.format_clzmsig(callee))


def list_literals(soot_dir, output_file):
    class_table = dict((clz, cd) \
            for clz, cd in jp.read_class_table_from_dir_iter(soot_dir))
    sb = cs.SummaryBuilder()
    for clz, cd in class_table.iteritems():
        for md in cd.methods.itervalues():
            sb.append_summary(jcte.extract_referred_literals(md.code, md, cd))
    literals = sb.to_summary().literals

    with open(output_file, "wb") as out:
        for lit in literals:
            out.write("%s\n" % lit)


def list_entry_points_from_node_summary(node_summary_file, output_file, option_method_sig=False):
    with open_gziped_file_when_available(node_summary_file, "rb") as inp:
        # data = pickle.load(inp)  # very very slow in pypy
        data = pickle.loads(inp.read())
    entry_points = data[DATATAG_ENTRY_POINTS]

    with open(output_file, "wb") as out:
        for ep in sorted(entry_points):
            if not option_method_sig:
                out.write("%s\n" % jp.clzmsig_clz(ep))
            else:
                out.write("%s\n" % jp.format_clzmsig(ep))


def list_methods_from_node_summary(node_summary_file, output_file):
    with open_gziped_file_when_available(node_summary_file, "rb") as inp:
        # data = pickle.load(inp)  # very very slow in pypy
        data = pickle.loads(inp.read())
    entry_points = data[DATATAG_ENTRY_POINTS]
    summary_table = data[DATATAG_NODE_SUMMARY]
    del data

    sb = cs.SummaryBuilder()
    for ep in entry_points:
        ep_with_possible_recursive_cxts = [(ep, None), (ep, ep)]
        for ep_w_rc in ep_with_possible_recursive_cxts:
            sumry = summary_table.get(ep_w_rc)
            if sumry:
                sumry.literals = ()
                sb.append_summary(sumry)
    callees = sb.to_summary().callees

    with open(output_file, "wb") as out:
        for callee in callees:
            out.write("%s\n" % jp.format_clzmsig(callee))


def list_literals_from_node_summary(node_summary_file, output_file):
    with open_gziped_file_when_available(node_summary_file, "rb") as inp:
        # data = pickle.load(inp)  # very very slow in pypy
        data = pickle.loads(inp.read())
    entry_points = data[DATATAG_ENTRY_POINTS]
    summary_table = data[DATATAG_NODE_SUMMARY]
    del data

    sb = cs.SummaryBuilder()
    for ep in entry_points:
        ep_with_possible_recursive_cxts = [(ep, None), (ep, ep)]
        for ep_w_rc in ep_with_possible_recursive_cxts:
            sumry = summary_table.get(ep_w_rc)
            if sumry:
                sumry.callees = ()
                sb.append_summary(sumry)
    literals = sb.to_summary().literals

    with open(output_file, "wb") as out:
        for lit in literals:
            out.write("%s\n" % lit)


def measure_tree(node):
    cn2data = {}

    def measure_tree_i(node):
        # count_nodes, max_depth, max_length, max_width
        if isinstance(node, list):
            assert node
            n0 = node[0]
            if n0 == ct.ORDERED_AND:
                cn = md = ml = 0
                mw = 1
                for subn in node[1:]:
                    scn, smd, sml, smw = measure_tree_i(subn)
                    cn += scn
                    md = max(md, smd)
                    ml += sml
                    mw = max(mw, smw)
                return cn, md, ml, mw
            elif n0 == ct.ORDERED_OR:
                cn = md = ml = mw = 0
                for subn in node[1:]:
                    scn, smd, sml, smw = measure_tree_i(subn)
                    cn += scn
                    md = max(md, smd)
                    ml = max(ml, sml)
                    mw += smw
                return cn, md, ml, mw
            else:
                assert False
        elif isinstance(node, ct.CallNode):
            node_label = cb.callnode_label(node)
            d = cn2data.get(node_label)
            if not d:
                cn = md = ml = mw = 1
                if node.body:
                    scn, smd, sml, smw = measure_tree_i(node.body)
                    cn += scn
                    md += smd
                    ml = max(ml, sml)
                    mw = max(mw, smw)
                cn2data[node_label] = d = cn, md, ml, mw
            return d
        elif isinstance(node, ct.Invoked):
            return 1, 1, 1, 1
        else:
            assert False

    return measure_tree_i(node)

def get_calltree_staistics(call_tree_file, output_file):
    with open_gziped_file_when_available(call_tree_file, "rb") as inp:
        # data = pickle.load(inp)  # very very slow in pypy
        data = pickle.loads(inp.read())
    call_trees = data[DATATAG_CALL_TREES]
    #ce = data[DATATAG_ENTRY_POINTS]
    del data

    with open(output_file, "wb") as out:
        count_entry_points = len(call_trees)
        out.write("entry_points\t%d\n" % count_entry_points)
        out.write("\n")
        out.write("%s\n" % "\t".join(["entry_point", "nodes", "depth", "length", "width"]))
        for n in call_trees:
            count_nodes, max_depth, max_length, max_width = measure_tree(n)
            out.write("%s\n" % "\t".join([
                    jp.format_clzmsig(n.invoked.callee),
                    "%d" % count_nodes,
                    "%d" % max_depth,
                    "%d" % max_length,
                    "%d" % max_width
            ]))


def main(argv):
    NotGiven = object()

    psr = argparse.ArgumentParser(prog=argv[0], description='agoat diagnostic')
    subpsrs = psr.add_subparsers(dest='command', help='commands')

    psr_ep = subpsrs.add_parser('entrypoint', help='listing entry points')
    g = psr_ep.add_mutually_exclusive_group()
    g.add_argument('-s', '--soot-dir', action='store', nargs='?', help='soot directory', default=NotGiven)
    g.add_argument('-n', '--node-summary', action='store', nargs='?', help='call-tree file', default=NotGiven)
    psr_ep.add_argument('-o', '--output', action='store', default=STDOUT)
    psr_ep.add_argument('-m', '--method-sig', action='store_true', help="output method signatures")

    psr_mt = subpsrs.add_parser('method', help='listing methods')
    g = psr_mt.add_mutually_exclusive_group()
    g.add_argument('-s', '--soot-dir', action='store', nargs='?', help='soot directory', default=NotGiven)
    g.add_argument('-n', '--node-summary', action='store', nargs='?', help='call-tree file', default=NotGiven)
    psr_mt.add_argument('-o', '--output', action='store', default=STDOUT)

    psr_lt = subpsrs.add_parser('literal', help='listing literals')
    g = psr_lt.add_mutually_exclusive_group()
    g.add_argument('-s', '--soot-dir', action='store', nargs='?', help='soot directory', default=NotGiven)
    g.add_argument('-n', '--node-summary', action='store', nargs='?', help='call-tree file', default=NotGiven)
    psr_lt.add_argument('-o', '--output', action='store', default=STDOUT)

    psr_cs = subpsrs.add_parser("size", help='call-tree statistics')
    psr_cs.add_argument('-c', '--call-tree', action='store', 
            help="call-tree file. (default '%s')" % _c.default_calltree_path,
            default=_c.default_calltree_path)
    psr_cs.add_argument('-o', '--output', action='store', default=STDOUT)

    psr_db = subpsrs.add_parser('debug', help='debug function')
    psr_db.add_argument('-p', '--pretty-print', action='store', help='pretty print internal data')

    args = psr.parse_args(argv[1:])
    if args.command == 'entrypoint':
        if args.soot_dir is not NotGiven:
            soot_dir = _c.default_soot_dir_path if args.soot_dir is None else args.soot_dir
            list_entry_points(soot_dir, args.output, args.method_sig)
        elif args.node_summary is not NotGiven:
            node_summary_file = _c.default_summary_path if args.node_summary is None else args.node_summary
            list_entry_points_from_node_summary(node_summary_file, args.output, args.method_sig)
        else:
            sys.exit("need either -s or -n")
    elif args.command == 'method':
        if args.soot_dir is not NotGiven:
            soot_dir = _c.default_soot_dir_path if args.soot_dir is None else args.soot_dir
            list_methods(soot_dir, args.output)
        elif args.node_summary is not NotGiven:
            node_summary_file = _c.default_summary_path if args.node_summary is None else args.node_summary
            list_methods_from_node_summary(node_summary_file, args.output)
        else:
            sys.exit("need either -s or -n")
    elif args.command == 'literal':
        if args.soot_dir is not NotGiven:
            soot_dir = _c.default_soot_dir_path if args.soot_dir is None else args.soot_dir
            list_literals(soot_dir, args.output)
        elif args.node_summary is not NotGiven:
            node_summary_file = _c.default_summary_path if args.node_summary is None else args.node_summary
            list_literals_from_node_summary(node_summary_file, args.output)
        else:
            sys.exit("need either -s or -n")
    elif args.command == 'size':
        get_calltree_staistics(args.call_tree, args.output)
    elif args.command == 'debug':
        if args.pretty_print:
            data_file = args.pretty_print 
            if data_file.endswith(".gz"):
                data_file = data_file[:-len(".gz")]
            pretty_print_raw_data_file(data_file)
        else:
            sys.exit("nothing to do")
    else:
        assert False
