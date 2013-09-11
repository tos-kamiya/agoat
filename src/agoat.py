#coding: utf-8

import os
import sys
import argparse
import pickle

from _utilities import open_w_default

import andor_tree_query as atq
import jimp_parser as jp
import jimp_code_term_extractor as jcte
import calltree as ct
import calltree_builder as cb
import calltree_summarizer as cs
import calltree_query as cq
import src_linenumber_converter as slc


def pretty_print_pickle_data(data_file, out=sys.stdout):
    import pprint

    with open_w_default(data_file, "rb", sys.stdin) as inp:
        data = pickle.load(inp)
    pp = pprint.PrettyPrinter(indent=4, stream=out)
    pp.pprint(data)


def format_clz_msig(clz, msig):
    return "%s %s %s(%s)" % (clz, jp.methodsig_retv(msig), jp.methodsig_name(msig), ','.join(jp.methodsig_params(msig)))


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


def generate_call_tree_and_node_summary(entry_point_classes, soot_dir, output_file):
    class_table = dict((clz, cd) \
            for clz, cd in jp.read_class_table_from_dir_iter(soot_dir))

    entry_points = cb.find_entry_points(class_table, target_class_names=entry_point_classes)

    class_table = cb.inss_to_tree_in_class_table(class_table)
    call_trees = cb.extract_call_andor_trees(class_table, entry_points)
    node_summary_table = {}
    for call_tree in call_trees:
        node_summary_table = cs.extract_node_summary_table(call_tree, summary_memo=node_summary_table)
        assert None not in node_summary_table  # debug

    with open_w_default(output_file, "wb", sys.stdout) as out:
        pickle.dump((call_trees, node_summary_table), out)


def generate_linenumber_table(soot_dir, javap_dir, output_file):
    assert os.path.isdir(soot_dir)
    assert os.path.isdir(javap_dir)

    class_table = dict((clz, cd) \
            for clz, cd in jp.read_class_table_from_dir_iter(soot_dir))
    claz_msig2invocationindex2linenum = slc.make_invocationindex_to_src_linenum_table(javap_dir)
    clz_msig2conversion = slc.jimp_linnum_to_src_linenum_table(class_table, claz_msig2invocationindex2linenum)

    with open_w_default(output_file, "wb", sys.stdout) as out:
        pickle.dump(clz_msig2conversion, out)


def mark_uncontributing_nodes_w_call_wo_memo(call_node, query_patterns):
    len_query_patterns = len(query_patterns)
    def predicate_func(node):
        if isinstance(node, ct.CallNode):
            invoked = node.invoked
            clz, msig = invoked[1], invoked[2]
            b = mark_uncontributing_nodes_w_call_i(node.body)
            recv_body_contributing = not isinstance(b, cq.Uncontributing)
            if recv_body_contributing:
                n = ct.CallNode(invoked, node.recursive_cxt, b)
            else:
                if len(cq.missing_query_words([(clz, msig)], query_patterns)) < len_query_patterns:
                    n = ct.CallNode(invoked, node.recursive_cxt, cq.Uncontributing([ct.ORDERED_AND]))
                else:
                    n = cq.Uncontributing(node)
            return atq.HookResult(n)
        elif isinstance(node, tuple) and node and node[0] in (jp.INVOKE, jp.SPECIALINVOKE):
            clz, msig = node[1], node[2]
            return len(cq.missing_query_words([(clz, msig)], query_patterns)) < len_query_patterns
        else:
            return atq.Undecided
    def mark_uncontributing_nodes_w_call_i(node):
        return atq.mark_uncontributing_nodes(node, predicate_func)
    return mark_uncontributing_nodes_w_call_i(call_node)


def format_call_tree_node(node, out=sys.stdout, indent_width=2, clz_msig2conversion=None):
    if clz_msig2conversion:
        def format_loc_info(loc_info):
            if loc_info is None:
                return "-"
            clz, msig, jimp_linenum_str = loc_info.split('\n')
            jimp_linenum = int(jimp_linenum_str)
            conv = clz_msig2conversion.get((clz, msig))
            src_linenum = conv[jimp_linenum] if conv else "*"
            return "%s\t(line: %s)" % (format_clz_msig(clz, msig), src_linenum)
    else:
        def format_loc_info(loc_info):
            if loc_info is None:
                return "-"
            clz, msig, jimp_linenum_str = loc_info.split('\n')
            return "%s" % (format_clz_msig(clz, msig))

    indent_step_str = ' ' * indent_width
    def format_i(node, indent):
        if isinstance(node, list):
            assert node
            n0 = node[0]
            if n0 == ct.ORDERED_OR:
                contributing_subn = [subn for subn in node[1:] if not isinstance(subn, cq.Uncontributing)]
                if len(contributing_subn) >= 2:
                    out.write('%s||\n' % (indent_step_str * indent))
                    for subn in contributing_subn:
                        format_i(subn, indent + 1)
                elif contributing_subn:
                    format_i(contributing_subn[0], indent)
            elif n0 == ct.ORDERED_AND:
                for subn in node[1:]:
                    if isinstance(subn, cq.Uncontributing):
                        pass
                    else:
                        format_i(subn, indent)
            else:
                assert False
        elif isinstance(node, ct.CallNode):
            invoked = node.invoked
            clz, msig, loc_info = invoked[1], invoked[2], invoked[4]
            indent_str = indent_step_str * indent
            out.write('%s%s\t%s\n' % (indent_str, format_clz_msig(clz, msig), format_loc_info(loc_info)))
            body = node[3]
            if not (isinstance(body, cq.Uncontributing) or isinstance(body, list) and len(body) <= 1):
                out.write('%s{\n' % indent_str)
                format_i(body, indent + 1)
                out.write('%s}\n' % indent_str)
        elif isinstance(node, tuple):
            assert node
            n0 = node[0]
            assert n0 in (jp.INVOKE, jp.SPECIALINVOKE)
            clz, msig, loc_info = invoked[1], invoked[2], invoked[4]
            out.write('%s%s\t%s\n' % (indent_step_str * indent, format_clz_msig(clz, msig), format_loc_info(loc_info)))
        elif isinstance(node, cq.Uncontributing):
            assert False
        else:
            assert False

    return format_i(node, 0)
# 
# 
# def node_complexity(node):
#     if isinstance(node, list):
#         n0 = node[0]
#         if n0 in (atq.ORDERED_AND, atq.ORDERED_OR):
#             depth, branch, tot_node, uncontributings = 0, 0, 0, 0
#             for subn in node[1:]:
#                 d, b, tn, uc = node_complexity(subn)
#                 if d > depth:
#                     depth = d
#                 branch += b
#                 tot_node += tn
#                 uncontributings = uc
#             return depth, branch, tot_node, uncontributings
#         elif n0 == cb.CALL:
#             assert node[2][0] in (jp.INVOKE, jp.SPECIALINVOKE)
#             subnode = node[3]
#             if subnode == cb.NOTREE:
#                 raise ValueError("NOTREE not yet supported")
#             elif isinstance(subnode, list):
#                 d, b, tn, uc = node_complexity(subnode)
#                 return d + 1, b, 1 + tn, uc
#             elif isinstance(subnode, cq.Uncontributing): 
#                 return 1, 0, 0, 1
#             else:
#                 return 1, 0, 1, 0
#         elif n0 == cb.NOTREE:
#             raise ValueError("NOTREE not yet supported")
#     elif isinstance(node, cq.Uncontributing): 
#         return 0, 0, 0, 1
#     return 1, 0, 1, 0


def format_call_tree_node_compact(node, out=sys.stdout, indent_width=2, clz_msig2conversion=None):
    if clz_msig2conversion:
        def format_loc_info(loc_info):
            if loc_info is None:
                return "-"
            clz, msig, jimp_linenum_str = loc_info.split('\n')
            jimp_linenum = int(jimp_linenum_str)
            conv = clz_msig2conversion.get((clz, msig))
            src_linenum = conv[jimp_linenum] if conv else "*"
            return "(line: %s)" % src_linenum
    else:
        def format_loc_info(loc_info):
            return ""

    printed_node_labels = set()

    def format_i(node):
        if isinstance(node, list):
            assert node
            n0 = node[0]
            if n0 == ct.ORDERED_OR:
                subouts = []
                for subn in node[1:]:
                    b = format_i(subn)
                    if b:
                        subouts.append(b)
                if len(subouts) >= 2:
                    r = [(0, '||', '')]
                    for buf in subouts:
                        for p in buf:
                            r.append((p[0] + 1, p[1], p[2]))
                    return r
                elif len(subouts) == 1:
                    return subouts[0]
                return None
            elif n0 == ct.ORDERED_AND:
                buf = []
                for subn in node[1:]:
                    b = format_i(subn)
                    if b:
                        buf.extend(b)
                if buf:
                    return buf
                return None
            else:
                assert False
        elif isinstance(node, ct.CallNode):
            invoked = node.invoked
            clz, msig, loc_info = invoked[1], invoked[2], invoked[4]
            node_label = cb.callnode_label(node)
            if node_label not in printed_node_labels:
                printed_node_labels.add(node_label)
                buf = [(0, '%s {' % format_clz_msig(clz, msig), format_loc_info(loc_info))]
                b = format_i(node.body)
                if b:
                    for p in b:
                        buf.append((p[0] + 1, p[1], p[2]))
                    buf.append((0, '}', ''))
                else:
                    p = buf[-1]
                    buf[-1] = (p[0], p[1] + '}', p[2])
                return buf
            return None
        elif isinstance(node, tuple):
            assert node
            n0 = node[0]
            assert n0 in (jp.INVOKE, jp.SPECIALINVOKE)
            clz, msig, loc_info = node[1], node[2], node[4]
            node_label = (clz, msig, None)  # context unknown, use non-context as default
            if node_label not in printed_node_labels:
                printed_node_labels.add(node_label)
                return [(0, format_clz_msig(clz, msig), format_loc_info(loc_info))]
            return None
        elif isinstance(node, cq.Uncontributing):
            return None
        else:
            assert False

    assert isinstance(node, ct.CallNode)
    clz, msig = node.invoked[1], node.invoked[2]
    node_label = cb.callnode_label(node)
    printed_node_labels.add(node_label)
    line_depth_body_locinfos = [(0, '%s {' % format_clz_msig(clz, msig), '')]
    buf = format_i(node.body)
    if buf:
        for p in buf:
            line_depth_body_locinfos.append((p[0] + 1, p[1], p[2]))
    line_depth_body_locinfos.append((0, '}', ''))

    indent_step_str = '  '
    for d, b, locinfo in line_depth_body_locinfos:
        out.write('%s%s\t%s\n' % (indent_step_str * d, b, locinfo))


def search_method_bodies(call_tree_file, query_words, output_file, ignore_case=False, line_number_table=None, max_depth=-1):
    with open_w_default(call_tree_file, "rb", sys.stdin) as inp:
        call_trees, node_summary_table = pickle.load(inp)

    clz_msig2conversion = None
    if line_number_table is not None:
        with open_w_default(line_number_table, "rb", sys.stdin) as inp:
            clz_msig2conversion = pickle.load(inp)

    query_patterns = cq.build_query_pattern_list(query_words, ignore_case=ignore_case)
    call_nodes = cq.find_lower_call_nodes(query_patterns, call_trees, node_summary_table)
    shallowers = filter(None, (cq.extract_shallowest_treecut(call_node, query_patterns, max_depth) for call_node in call_nodes))
    markeds = [mark_uncontributing_nodes_w_call_wo_memo(shallower, query_patterns) for shallower in shallowers]

    with open_w_default(output_file, "wb", sys.stdout) as out:
        for marked in sorted(markeds):
            out.write("---\n")
            format_call_tree_node_compact(marked, out, clz_msig2conversion=clz_msig2conversion)
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
    subpsrs = psr.add_subparsers(dest='command', help='commands')

    psr_ep = subpsrs.add_parser('e', help='listing entry point classes')
    psr_ep.add_argument('-s', '--soot-dir', action='store', help='soot directory', default='sootOutput')
    psr_ep.add_argument('-o', '--output', action='store', help="output file. '-' for standard output", default='-')
    psr_ep.add_argument('-m', '--method-sig', action='store_true', help="output method signatures")

    psr_mt = subpsrs.add_parser('m', help='listing methods (defined methods and used ones)')
    psr_mt.add_argument('-s', '--soot-dir', action='store', help='soot directory', default='sootOutput')
    psr_mt.add_argument('-o', '--output', action='store', help="output file. '-' for standard output", default='-')

    psr_sl = subpsrs.add_parser('l', help='generate line number table')
    psr_sl.add_argument('-s', '--soot-dir', action='store', help='soot directory', default='sootOutput')
    psr_sl.add_argument('-j', '--javap-dir', action='store', default=default_javap_dir_path)
    psr_sl.add_argument('-o', '--output', action='store', 
            help="output file. '-' for standard output. (default '%s')" % default_linenumbertable_path, 
            default=default_linenumbertable_path)

    psr_ct = subpsrs.add_parser('c', help='generate call tree and node summary table')
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
    psr_q.add_argument('-D', '--max-depth', action='store', type=int, 
            help="max depth of subtree. -1 for unlimited depth. (default is '%d')" % defalut_max_depth_of_subtree,
            default=defalut_max_depth_of_subtree)

    psr_db = subpsrs.add_parser('debug', help='debug function')
    psr_db.add_argument('-p', action='store', dest='internaldata', help='pretty print internal data')

    args = psr.parse_args(argv[1:])
    if args.command == 'e':
        list_entry_points(args.soot_dir, args.output, args.method_sig)
    elif args.command == 'm':
        list_methods(args.soot_dir, args.output)
    elif args.command == 'l':
        generate_linenumber_table(args.soot_dir, args.javap_dir, args.output)
    elif args.command == 'c':
        generate_call_tree_and_node_summary(args.entrypointclasses, args.soot_dir, args.output)
    elif args.command == 'q':
        line_number_table = None
        if args.line_number_table is not None:
            line_number_table = args.line_number_table
        else:
            if os.path.exists(default_linenumbertable_path):
                line_number_table = default_linenumbertable_path
        search_method_bodies(args.call_tree, args.queryword, args.output, args.ignore_case, line_number_table, args.max_depth)
    elif args.command == 'debug':
        if args.internaldata:
            pretty_print_pickle_data(args.internaldata)
    else:
        assert False


if __name__ == '__main__':
    main(sys.argv)