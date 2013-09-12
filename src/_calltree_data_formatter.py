#coding: utf-8

import pprint

import jimp_parser as jp
import calltree as ct
import calltree_builder as cb
import calltree_query as cq


DATATAG_CALL_TREES = "call_trees"
DATATAG_NODE_SUMMARY = "node_summary_table"
DATATAG_LINENUMBER_TABLE = "linenumber_table"


def format_clz_msig(clz, msig):
    return "%s %s %s(%s)" % (clz, jp.methodsig_retv(msig), jp.methodsig_name(msig), ','.join(jp.methodsig_params(msig)))


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
                if original_body_id != id(node.body):
                    assert False  #debug
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


def format_call_tree_node(node, out, indent_width=2, clz_msig2conversion=None):
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
            lits = invoked[3]
            if lits:
                out.write('%s    %s\n' % (indent_str, ', '.join(lits)))
            body = node.body
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
            lits = node[3]
            if lits:
                out.write('%s    %s\n' % (indent_str, ', '.join(lits)))
        elif isinstance(node, cq.Uncontributing):
            assert False
        else:
            assert False

    return format_i(node, 0)


def format_call_tree_node_compact(node, out, indent_width=2, clz_msig2conversion=None):
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

    def put_callnode(node, loc_info_str=None):
        invoked = node.invoked
        clz, msig = invoked[1], invoked[2]
        if loc_info_str is None:
            loc_info = invoked[4]
            loc_info_str = format_loc_info(loc_info)
        lits = invoked[3]
        node_label = label_w_lit(invoked, node.recursive_cxt)
        if node_label not in printed_node_label_w_lits:
            printed_node_label_w_lits.add(node_label)
            buf = [(0, '%s {' % format_clz_msig(clz, msig), loc_info_str)]
            if lits:
                buf.append((0, '    %s' % ', '.join(lits), ''))
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

    def put_tuple(node, loc_info_str=None):
        assert node
        n0 = node[0]
        assert n0 in (jp.INVOKE, jp.SPECIALINVOKE)
        clz, msig = node[1], node[2]
        if loc_info_str is None:
            loc_info = node[4]
            loc_info_str = format_loc_info(loc_info)
        lits = node[3]
        node_label = label_w_lit(node, None)  # context unknown, use non-context as default
        if node_label not in printed_node_label_w_lits:
            printed_node_label_w_lits.add(node_label)
            buf = [(0, format_clz_msig(clz, msig), loc_info_str)]
            if lits:
                buf.append((0, '    %s' % ', '.join(lits), ''))
            return buf
        return None

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
            return put_callnode(node)
        elif isinstance(node, tuple):
            return put_tuple(node)
        elif isinstance(node, cq.Uncontributing) or node is None:
            return None
        else:
            assert False

    if isinstance(node, ct.CallNode):
        buf = put_callnode(node, loc_info_str='')
    elif isinstance(node, tuple):
        buf = put_tuple(node, loc_info_str='')
    else:
        assert False

    assert buf is not None
    indent_step_str = '  '
    for d, b, locinfo in buf:
        out.write('%s%s\t%s\n' % (indent_step_str * d, b, locinfo))

