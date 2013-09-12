#coding: utf-8

import pprint
import colorama

import jimp_parser as jp
import calltree as ct
import calltree_builder as cb


DATATAG_CALL_TREES = "call_trees"
DATATAG_NODE_SUMMARY = "node_summary_table"
DATATAG_LINENUMBER_TABLE = "linenumber_table"


def init_ansi_color():
    colorama.init()


def format_clz_msig(clz, msig):
    return "%s %s %s(%s)" % (clz, jp.methodsig_retv(msig), jp.methodsig_name(msig), ','.join(jp.methodsig_params(msig)))
def format_clz(clz): return clz
def format_msig(msig): return "%s %s(%s)" % (jp.methodsig_retv(msig), jp.methodsig_name(msig), ','.join(jp.methodsig_params(msig)))


OMITTED_PACKAGES = ["java.lang."]
_OMITTING_TABLE = [(p, len(p)) for p in OMITTED_PACKAGES]


def omit_trivial_pakcage(s):
    for p, lp in _OMITTING_TABLE:
        if s.startswith(p):
            return s[lp:]
    return s


def format_clz_msig_with_omitting_trivial_pakcage(clz, msig):
    return "%s %s %s(%s)" % (omit_trivial_pakcage(clz), 
        omit_trivial_pakcage(jp.methodsig_retv(msig)), 
        jp.methodsig_name(msig), 
        ','.join(omit_trivial_pakcage(t) for t in jp.methodsig_params(msig))
    )
def format_clz_with_omitting_trivial_pakcage(clz): return omit_trivial_pakcage(clz) 
def format_msig_with_omitting_trivial_pakcage(msig):
    return "%s %s(%s)" % (omit_trivial_pakcage(jp.methodsig_retv(msig)), 
        jp.methodsig_name(msig), 
        ','.join(omit_trivial_pakcage(t) for t in jp.methodsig_params(msig))
    )


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
                if not body or isinstance(body, tuple):
                    label_to_body_tbl[node_label] = id(body), body
                elif isinstance(body, (list, ct.CallNode)):
                    label_to_body_tbl[node_label] = id(body), replace_i(body)
                else:
                    assert False
            else:
                original_body_id, transformed_body = e
                assert original_body_id == id(node.body)
            return ct.CallNode(node.invoked, node.recursive_cxt, ct.Node(node_label))
        else:
            return node
    return replace_i(node), label_to_body_tbl


def pretty_print_pickle_data(data, out):
    pp = pprint.PrettyPrinter(indent=4, stream=out)

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
        for node_label, summary in node_summary.iteritems():
            out.write("node summary:\n")
            pp.pprint((node_label, summary))
            out.write("\n")


def make_custom_formatters(contribution_data, fully_qualified_package_name, ansi_color):
    _, cont_clzs, cont_msigs, cont_literals = contribution_data

    c_red = colorama.Fore.RED
    c_reset = colorama.Fore.RESET

    if fully_qualified_package_name:
        fmt_clz, fmt_msig = format_clz, format_msig
    else:
        fmt_clz, fmt_msig = format_clz_with_omitting_trivial_pakcage, format_msig_with_omitting_trivial_pakcage
    if ansi_color:
        old_fmt_clz, old_fmt_msig = fmt_clz, fmt_msig
        def fmt_clz_w_coloring(clz):
            s = old_fmt_clz(clz)
            return (c_red + s + c_reset) if clz in cont_clzs else s
        def fmt_msig_w_coloring(msig):
            s = old_fmt_msig(msig)
            return (c_red + s + c_reset) if msig in cont_msigs else s
        fmt_clz, fmt_msig = fmt_clz_w_coloring, fmt_msig_w_coloring

    if ansi_color:
        def fmt_lits(lits):
            if lits not in cont_literals:
                return None
            s = ', '.join(lits)
            return c_red + s + c_reset
    else:
        def fmt_lits(lits):
            if lits not in cont_literals:
                return None
            return ', '.join(lits)

    return fmt_clz, fmt_msig, fmt_lits


def format_call_tree_node_compact(node, out, contribution_data, indent_width=2, clz_msig2conversion=None, 
        fully_qualified_package_name=False, ansi_color=False):
    node_id_to_cont, cont_clzs, cont_msigs, _ = contribution_data

    fmt_clz, fmt_msig, fmt_lits = make_custom_formatters(contribution_data, fully_qualified_package_name, ansi_color)

    def label_w_lit(invoked, recursive_cxt):
        items = [recursive_cxt, invoked[1], invoked[2]]
        invoked[3] and items.extend(invoked[3])
        return tuple(items)

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

    printed_node_label_w_lits = set()

    def put_callnode(node, loc_info_str):
        invoked = node.invoked
        clz, msig = invoked[1], invoked[2]
        if loc_info_str is None:
            loc_info_str = format_loc_info(invoked[4])
        node_label = label_w_lit(invoked, node.recursive_cxt)
        if node_label not in printed_node_label_w_lits:
            buf = [(0, '%s %s {' % (fmt_clz(clz), fmt_msig(msig)), loc_info_str)]
            s = fmt_lits(invoked[3])
            if s:
                buf.append((0, '    ' + s, ''))
            b = format_i(node.body)
            if b:
                buf.extend((p[0] + 1, p[1], p[2]) for p in b)
                buf.append((0, '}', ''))
            elif clz in cont_clzs or msig in cont_msigs:
                p = buf[-1]
                buf[-1] = (p[0], p[1] + '}', p[2])
            else:
                return None
            printed_node_label_w_lits.add(node_label)
            return buf
        return None

    def put_tuple(node, loc_info_str):
        assert node
        assert node[0] in (jp.INVOKE, jp.SPECIALINVOKE)
        if loc_info_str is None:
            loc_info_str = format_loc_info(node[4])
        node_label = label_w_lit(node, None)  # context unknown, use non-context as default
        if node_label not in printed_node_label_w_lits:
            printed_node_label_w_lits.add(node_label)
            buf = [(0, '%s %s' % (fmt_clz(node[1]), fmt_msig(node[2])), loc_info_str)]
            s = fmt_lits(node[3])
            if s:
                buf.append((0, '    ' + s, ''))
            return buf
        return None

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
        elif isinstance(node, tuple):
            return put_tuple(node, None)
        else:
            assert None

    if isinstance(node, ct.CallNode):
        buf = put_callnode(node, '')
    elif isinstance(node, tuple):
        buf = put_tuple(node, '')
    else:
        assert False

    assert buf is not None
    indent_step_str = '  '
    for d, b, locinfo in buf:
        out.write('%s%s\t%s\n' % (indent_step_str * d, b, locinfo))

