#coding: utf-8

import collections
import pprint

try:
    import colorama
except:
    colorama = None  # O.K., goes w/o colorama

from . import jimp_parser as jp
from . import calltree as ct
from . import calltree_builder as cb
from . import calltree_query as cq

DATATAG_ENTRY_POINTS = "entry_points"
DATATAG_CALL_TREES = "call_trees"
DATATAG_NODE_SUMMARY = "node_summary_table"
DATATAG_LINENUMBER_TABLE = "linenumber_table"


def init_ansi_color():
    import colorama  # ensure colorama is loaded. otherwise, runtime error
    colorama.init()


Node = collections.namedtuple('Node', 'label')


def replace_callnode_body_with_label(node, label_to_body_tbl={}):
    # label_to_body_tbl  # node_label -> (object id of original body, transformed body)
    def replace_i(node):
        if isinstance(node, list):
            assert node
            assert node[0] in (ct.ORDERED_AND, ct.ORDERED_OR)
            t = [node[0]]
            for subn in node[1:]:
                t.append(replace_i(subn))
            return t
        elif isinstance(node, ct.CallNode):
            node_label = cb.callnode_label(node)
            e = label_to_body_tbl.get(node_label)
            if not e:
                body = node.body
                if not body or isinstance(body, ct.Invoked):
                    label_to_body_tbl[node_label] = id(body), body
                elif isinstance(body, (list, ct.CallNode)):
                    label_to_body_tbl[node_label] = id(body), replace_i(body)
                else:
                    assert False
            else:
                original_body_id, transformed_body = e
                assert original_body_id == id(node.body)
            return ct.CallNode(node.invoked, node.recursive_cxt, Node(node_label))
        else:
            return node
    return replace_i(node), label_to_body_tbl


def pretty_print_raw_data(data, out):
    pp = pprint.PrettyPrinter(indent=4, stream=out)

    entry_points = data.get(DATATAG_ENTRY_POINTS)
    if entry_points:
        for entry_point in entry_points:
            out.write("entry point:\n")
            pp.pprint(entry_point)
            out.write("\n")

    call_trees = data.get(DATATAG_CALL_TREES)
    if call_trees:
        label_to_body_tbl = {}
        for call_tree in call_trees:
            n = replace_callnode_body_with_label(call_tree, label_to_body_tbl)[0]
            out.write("root node:\n")
            pp.pprint(n)
            out.write("\n")
        for node_label, (original_body_id, transformed_body) in sorted(label_to_body_tbl.iteritems(), key=lambda l_id_b: repr(l_id_b[0])):
            out.write("node:\n")
            pp.pprint((node_label, transformed_body))
            out.write("\n")

    node_summary = data.get(DATATAG_NODE_SUMMARY)
    if node_summary:
        for node_label, sumry in node_summary.iteritems():
            out.write("node summary:\n")
            pp.pprint((node_label, sumry))
            out.write("\n")

    linenumber_table = data.get(DATATAG_LINENUMBER_TABLE)
    if linenumber_table:
        out.write("linenumber table:\n")
        pp.pprint(linenumber_table)
        out.write("\n")


def gen_custom_formatters(query, fully_qualified_package_name, ansi_color):
    if ansi_color:
        a_enhanced = colorama.Fore.RED + colorama.Style.BRIGHT
        a_reset = colorama.Fore.RESET + colorama.Style.RESET_ALL

    if not fully_qualified_package_name:
        if ansi_color:
            def fmt_type(typ):
                if query.matches_type(typ):
                    return a_enhanced + jp.omit_trivial_package(typ) + a_reset
                else:
                    return jp.omit_trivial_package(typ)
        else:
            def fmt_type(typ):
                return jp.omit_trivial_package(typ)
    else:
        if ansi_color:
            def fmt_type(typ):
                if query.matches_type(typ):
                    return a_enhanced + typ + a_reset
                else:
                    return typ
        else:
            def fmt_type(typ):
                return typ

    if ansi_color:
        def fmt_method_name(m):
            if query.matches_method(m):
                return a_enhanced + m + a_reset
            else:
                return m
    else:
        def fmt_method_name(m):
            return m

    if ansi_color:
        def fmt_lits(lits):
            buf = []
            matched_found = False
            for lit in lits:
                if query.matches_literal(lit):
                    buf.append(a_enhanced + lit + a_reset)
                    matched_found = True
                else:
                    buf.append(lit)
            if matched_found:
                return ', '.join(buf)
            else:
                return None
    else:
        def fmt_lits(lits):
            for lit in lits:
                if query.matches_literal(lit):
                    return ', '.join(lits)
            else:
                return None

    if ansi_color:
        def fmt_clzmsig(clzmsig):
            m = jp.clzmsig_method(clzmsig)
            if not query.matches_method(m) and query.matches_method(m, callee=clzmsig):
                return (a_enhanced + "%s %s %s(%s)" + a_reset) % (
                    jp.clzmsig_clz(clzmsig),
                    jp.clzmsig_retv_str(clzmsig),
                    jp.clzmsig_method(clzmsig),
                    ','.join(jp.clzmsig_params(clzmsig))
                )
            else:
                return "%s %s %s(%s)" % (
                    fmt_type(jp.clzmsig_clz(clzmsig)),
                    fmt_type(jp.clzmsig_retv_str(clzmsig)),
                    fmt_method_name(jp.clzmsig_method(clzmsig)),
                    ','.join(fmt_type(typ) for typ in jp.clzmsig_params(clzmsig))
                )
    else:
        def fmt_clzmsig(clzmsig):
            return "%s %s %s(%s)" % (
                fmt_type(jp.clzmsig_clz(clzmsig)),
                fmt_type(jp.clzmsig_retv_str(clzmsig)),
                fmt_method_name(jp.clzmsig_method(clzmsig)),
                ','.join(fmt_type(typ) for typ in jp.clzmsig_params(clzmsig))
            )
    return fmt_type, fmt_clzmsig, fmt_lits


def format_call_tree_node_compact(node, out, query,
        indent_width=2, clz_msig2conversion=None, fully_qualified_package_name=False, ansi_color=False):

    node_id_to_cont = cq.extract_node_contribution(node, query)
    fmt_typ, fmt_clzmsig, fmt_lits = gen_custom_formatters(query, fully_qualified_package_name, ansi_color)

    def label_w_lit(clzmsig, recursive_cxt):
        return (recursive_cxt, clzmsig)

    if clz_msig2conversion:
        def format_loc_info(loc_info):
            if loc_info is None:
                return "-"
            clzmsig, jimp_linenum_str = loc_info.split('\n')
            jimp_linenum = int(jimp_linenum_str)
            conv = clz_msig2conversion.get(clzmsig)
            src_linenum = conv[jimp_linenum] if conv else "*"
            return "(line: %s)" % src_linenum
    else:
        def format_loc_info(loc_info):
            return ""

    def put_callnode(node, loc_info_str):
        invoked = node.invoked
        if loc_info_str is None:
            loc_info_str = format_loc_info(invoked.locinfo)
        buf = [(0, '%s {' % fmt_clzmsig(invoked.callee), loc_info_str)]
        s = fmt_lits(invoked.literals)
        if s:
            buf.append((0, '    ' + s, ''))
        b = format_i(node.body)
        if b:
            buf.extend((p[0] + 1, p[1], p[2]) for p in b)
            buf.append((0, '}', ''))
        elif node_id_to_cont.get(id(node)):
            p = buf[-1]
            buf[-1] = (p[0], p[1] + '}', p[2])
        else:
            return None
        return buf

    def put_invoked(node, loc_info_str):
        assert node
        if loc_info_str is None:
            loc_info_str = format_loc_info(node.locinfo)
        buf = [(0, fmt_clzmsig(node.callee), loc_info_str)]
        s = fmt_lits(node.literals)
        if s:
            buf.append((0, '    ' + s, ''))
        return buf

    def format_i(node):
        if not node or node is None or not node_id_to_cont[id(node)]:
            return None
        if isinstance(node, list):
            assert node
            n0 = node[0]
            if n0 in (ct.ORDERED_AND, ct.ORDERED_OR):
                count_of_valid_subitems = 0
                buf = []
                for subn in node[1:]:
                    b = format_i(subn)
                    if b:
                        count_of_valid_subitems += 1
                        buf.extend(b)
                if n0 == ct.ORDERED_OR:
                    if count_of_valid_subitems >= 2:
                        t = [(0, '||', '')]
                        t.extend((p[0] + 1, p[1], p[2]) for p in buf)
                        return t
                    elif count_of_valid_subitems == 0:
                        return None
                return buf
        elif isinstance(node, ct.CallNode):
            return put_callnode(node, None)
        elif isinstance(node, ct.Invoked):
            return put_invoked(node, None)
        else:
            assert None

    if isinstance(node, ct.CallNode):
        buf = put_callnode(node, '')
    elif isinstance(node, tuple):
        buf = put_invoked(node, '')
    else:
        assert False

    assert buf is not None
    indent_step_str = '  '
    for d, b, locinfo in buf:
        out.write('%s%s\t%s\n' % (indent_step_str * d, b, locinfo))