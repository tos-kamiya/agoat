# coding: utf-8

import sys

import andor_tree as at
import jimp_parser as jp
import _jimp_code_body_to_tree_elem as jcbte
from _jimp_code_body_to_tree_elem import NOTREE, inss_to_tree, inss_to_tree_in_class_table  # re-export

def extract_class_hierarchy(class_table, include_indirect_decendants=True):
    # class_table  # str -> ClassData
    class_to_descendants = {}  # str -> set of str
    for clz, class_data in class_table.iteritems():
        if class_data.base_name:
            class_to_descendants.setdefault(class_data.base_name, set()).add(clz)

    if include_indirect_decendants:
        emptyset = set()
        while True:
            something_expanded = False
            for ds in class_to_descendants.itervalues():
                prev_size = len(ds)
                ds_expanded = set(ds)
                for d in ds:
                    ds_expanded.update(class_to_descendants.get(d, emptyset))
                if len(ds_expanded) != prev_size:
                    something_expanded = True
                ds.update(ds_expanded)
            if not something_expanded:
                break  # while True

    return class_to_descendants

# def interface_implementation_table(class_table):
# iterface_to_classes = {}  # str -> [str]
#     for clz, class_data in class_table.iteritems():
#         if class_data.interf_names:
#             for i in class_data.interf_names:
#                 iterface_to_classes.setdefault(i, []).add(clz)
#     return iterface_to_classes


def make_dispatch_table(class_to_methods, class_to_descendants, iterface_to_classes=None):
    # class_to_descendants  # str -> set of str
    # class_to_methods  # str -> [MethodSig]
    # interface_to_classes  # str -> set of str
    assert iterface_to_classes is None  # not yet implemented

    recv_method_to_defs = {}
    # recv_method_to_defs  # (str, MethodSig) -> [str]
    for clz_mtds in class_to_methods.iteritems():
        clz, mtds = clz_mtds
        assert clz
        cands = [clz]
        descends = class_to_descendants.get(clz)
        if descends:
            cands.extend(descends)
        for d in cands:
            for mtd in mtds:
                if mtd in class_to_methods.get(d, []):
                    recv_method_to_defs.setdefault((clz, mtd), []).append(d)
    for cs in recv_method_to_defs.itervalues():
        cs.sort()
    return recv_method_to_defs


def make_method_call_resolver(class_table, recv_method_to_defs):
    # class_table  # str -> ClassData
    # recv_method_to_defs  # (str, MethodSig) -> [str]
    def resolver(recv_msig, static_method=False):
        resolved = []
        recv, msig = recv_msig
        cands = [recv] if static_method else recv_method_to_defs.get(recv_msig, [])
        for clz in cands:
            cd = class_table.get(clz)
            if cd:
                md = cd.methods.get(msig)
                if md:
                    c_m = cd.class_name, md.method_sig
                    resolved.append((c_m, md))
        return resolved
    return resolver

# def generate_call_andor_tree(class_table, method_table, recv_method_to_defs, entry_point):
# class_table  # str -> ClassData
# method_table  # (str, MethodSig) -> aot
# recv_method_to_defs  # (str, MethodSig) -> [str]
# entry_point  # (str, MethodSig)
#     pass


def find_methods_involved_in_recursive_call_chain(entry_point, resolver,
          include_direct_recursive_calls=False):
    # entry_points  # list of (str, MethodSig)

    methods_searched = set()
    # set of (str, MethodSig) # methods involved in recursive call chain
    methods_ircc = set()

    clz0, mtd0 = entry_point
    e = resolver(entry_point, static_method=True)
    if not e:
        raise ValueError("entry_point not found")
    c_m0, md0 = e[0]
    aot = md0.code if md0 else None
    if aot is None:
        raise ValueError("entry_point not found")

    def dig_node(node, callee, stack):
        len_stack0 = len(stack)
        try:
            if isinstance(node, tuple):
                assert node
                cmd = node[0]
                if cmd == jp.SPECIALINVOKE:
                    receiver_class, mtd = node[1], node[2]
                    rc_mtd = (receiver_class, mtd)
                    if not include_direct_recursive_calls and rc_mtd == stack[-1]:
                        pass
                    else:
                        r = resolver(rc_mtd, static_method=True)
                        if r:
                            assert len(r) == 1
                            _, md = r[0]
                            dig_call(rc_mtd, md, stack)
                elif cmd == jp.INVOKE:
                    receiver_class, mtd = node[1], node[2]
                    rc_mtd = (receiver_class, mtd)
                    if not include_direct_recursive_calls and rc_mtd == stack[-1]:
                        pass
                    else:
                        r = resolver(rc_mtd)
                        for rc_mtd, md in r:
                            dig_call(rc_mtd, md, stack)
                elif cmd in (jp.LABEL, jp.RETURN, jp.THROW):
                    pass
                else:
                    # sys.stderr.write("node = %s\n" % repr(node))
                    assert False
            elif isinstance(node, list):
                assert node
                assert node[0] in (jcbte.ORDERED_AND, jcbte.ORDERED_OR)
                for item in node[1:]:
                    dig_node(item, callee, stack)
        finally:
            if len(stack) > len_stack0:
                stack[:] = stack[:len_stack0]

    def dig_call(rc_mtd, md, stack):
        len_stack0 = len(stack)
        try:
            aot = md.code
            if not aot:
                return
            try:
                i = stack.index(rc_mtd)
                methods_ircc.update(stack[i:])
                return
            except:
                pass
            if rc_mtd in methods_searched:
                return
            methods_searched.add(rc_mtd)
            stack.append(rc_mtd)
            dig_node(aot, rc_mtd, stack)
        finally:
            if len(stack) > len_stack0:
                stack[:] = stack[:len_stack0]

    stack_sentinel = None
    dig_call(c_m0, md0, [stack_sentinel])

    s = list(methods_ircc)
    s.sort()
    return s


def find_entry_points(class_table, target_class_names=None):
    # class_table  # str -> ClassData
    entrypoint_msigs = set([
        jp.MethodSig(None, "main", ("java.lang.String[]",)), 
        jp.MethodSig(None, "run", ()),
        jp.MethodSig(None, "<clinit>", ())
    ])
    entry_points = []

    if target_class_names is None:
        target_class_names = class_table.iterkeys()
    for clz in target_class_names:
        class_data = class_table.get(clz)
        if not class_data: continue
        for msig, md in class_data.methods.iteritems():
            if msig in entrypoint_msigs:
                entry_points.append((clz, msig))
    return entry_points


CALL = "call"


def build_call_andor_tree(entry_point, resolver, methods_ircc, call_node_memo={}):
    # entry_point  # (str, MethodSig)
    # methods_ircc  # set of (str, MethodSig)
    # call_node_memo = {}  # (str, MethodSig, recursive_context) -> node

    def dig_node(aot, recursive_context, clz_msig):
        if isinstance(aot, list):
            assert aot
            aot0 = aot[0]
            if aot0 in (at.ORDERED_AND, at.ORDERED_OR, jcbte.BLOCK):
                n = [aot0]
                for item in aot[1:]:
                    v = dig_node(item, recursive_context, clz_msig)
                    if v is not None:
                        n.append(v)
                if len(n) == 2:
                    return n[1]
                return n
            else:
                assert False
        elif isinstance(aot, tuple):
            assert aot
            cmd = aot[0]
            if cmd == jp.SPECIALINVOKE:
                recv_msig = tuple(aot[1:3])
                if recv_msig == clz_msig or recv_msig == recursive_context:
                    return None
                loc_info = '\n'.join([clz_msig[0], clz_msig[1], "%d" % aot[3]])
                v = dig_dispatch(cmd, recv_msig, recursive_context, loc_info)
            elif cmd == jp.INVOKE:
                recv_msig = tuple(aot[1:3])
                if recv_msig == clz_msig or recv_msig == recursive_context:
                    return None
                loc_info = '\n'.join([clz_msig[0], clz_msig[1], "%d" % aot[3]])
                v = dig_dispatch(cmd, recv_msig, recursive_context, loc_info)
            else:
                return None
                # loc_info = clz_msig, aot[-1]
                # return tuple(list(aot[:-1]) + [loc_info])
            if not v:
                loc_info = '\n'.join([clz_msig[0], clz_msig[1], "%d" % aot[3]])
                return tuple(list(aot[:-1]) + [loc_info])
            return v
        else:
            return None

    digging_calls = []
    def dig_dispatch(cmd, recv_msig, recursive_context, loc_info):
        cand_methods = resolver(recv_msig, static_method=(cmd == jp.SPECIALINVOKE))
        if not cand_methods:
            return None
        dispatch_node = [at.ORDERED_OR]
        for clz_method, md in cand_methods:
            rc = recursive_context
            if rc is None and clz_method in methods_ircc:
                rc = clz_method
            cn = [CALL, rc, (cmd, clz_method[0], clz_method[1], loc_info)]
            node_label = (clz_method[0], clz_method[1], rc)
            v = call_node_memo.get(node_label)
            if v is None:
                if md.code != jcbte.NOTREE:
                    if clz_method in digging_calls:
                        if rc is None:
                            assert clz_method == digging_calls[-1]  # direct recursion
                        v = [at.ORDERED_AND]
                    else:
                        digging_calls.append(clz_method)
                        v = dig_node(md.code, rc, clz_method)
                        digging_calls.pop()
                else:
                    v = jcbte.NOTREE  # can't expand
                call_node_memo[node_label] = v
            cn.append(v)
            dispatch_node.append(cn)
        len_dispatch_node = len(dispatch_node)
        if len_dispatch_node == 1:
            return None
        elif len_dispatch_node == 2:
            return dispatch_node[1]
        else:
            return dispatch_node

    return dig_dispatch(jp.SPECIALINVOKE, entry_point, None, None)


def extract_call_andor_trees(class_table, entry_points):
    class_to_descendants = extract_class_hierarchy(class_table)
    class_to_methods = dict((claz, cd.methods.keys()) for claz, cd in class_table.iteritems())
    # class_to_methods  # str -> [MethodSig]

    recv_method_to_defs = make_dispatch_table(class_to_methods, class_to_descendants)

    resolver = make_method_call_resolver(class_table, recv_method_to_defs)

    methods_ircc = set()
    for entry_point in entry_points:
        ms = find_methods_involved_in_recursive_call_chain(entry_point, resolver)
        methods_ircc.update(ms)
    methods_ircc = sorted(methods_ircc)
    # out.write("methods involved in recursive chain:\n")
    # for mtd in methods_ircc:
    #     out.write("  %s\n" % repr(mtd))

    call_trees = []
    call_node_memo = {}
    for entry_point in entry_points:
        call_tree = build_call_andor_tree(entry_point, resolver, methods_ircc, call_node_memo=call_node_memo)
        call_trees.append(call_tree)
    return call_trees


def main(argv, out=sys.stdout, logout=sys.stderr):
    import pprint

    dirname = argv[1]
    entry_point_class = argv[2] if len(argv) >= 3 else None
    entry_point_method = argv[3] if len(argv) >= 4 else None

    logout.write("> sootOutput-dir: %s\n" % dirname)
    class_table = {}
    for clz, cd in jp.read_class_table_from_dir_iter(dirname):
        # sys.stderr.write("> %s\n" % clz)
        class_table[clz] = cd

    if not entry_point_class:
        entry_points = find_entry_points(class_table)
        out.write("entry point classes:\n")
        for ep in sorted(entry_points):
            out.write("  %s\n" % ep[0])
        return

    if entry_point_method:
        entry_point_msig = None
        for cd in class_table.itervalues():
            if entry_point_msig:
                break  # for cd
            if cd.class_name == entry_point_class:
                for md in cd.methods.itervalues():
                    if entry_point_msig:
                        break  # for md
                    if jp.methodsig_name(md.method_sig).find(entry_point_method) >= 0:
                        entry_point_msig = md.method_sig
    else:
        entry_point_msig = jp.MethodSig(None, "main", ("java.lang.String[]",))
    entry_point = (entry_point_class, entry_point_msig)
    logout and logout.write("> entry point is: %s %s\n" % entry_point)

    logout and logout.write("> build aot\n")

    def progress_repo(current=None, canceled_becaseof_branches=None):
        if current:
            clz, msig = current
            sys.stderr.write(">   processing: %s %s\n" % (clz, msig))
        if canceled_becaseof_branches:
            clz, msig, branches = canceled_becaseof_branches
            sys.stderr.write(
                ">   canceled: %s %s (branches=%d)\n" % (clz, msig, branches))
    class_table = jcbte.inss_to_tree_in_class_table(class_table,
            branches_atmost=50, progress_repo=progress_repo)

    logout and logout.write("> extract hierachy\n")
    class_to_descendants = extract_class_hierarchy(class_table)
    logout and logout.write("> reslove dispatch\n")
    class_to_methods = dict((claz, cd.methods.keys())
            for claz, cd in class_table.iteritems())
    # class_to_methods  # str -> [MethodSig]

    recv_method_to_defs = make_dispatch_table(
        class_to_methods, class_to_descendants)

    logout and logout.write("> find recursive\n")
    resolver = make_method_call_resolver(class_table, recv_method_to_defs)
    methods_ircc = find_methods_involved_in_recursive_call_chain(
            entry_point, resolver)

    # out.write("methods involved in recursive chain:\n")
    # for mtd in methods_ircc:
    #     out.write("  %s\n" % repr(mtd))

    logout and logout.write("> build call and-or tree\n")
    call_tree = build_call_andor_tree(entry_point, resolver, methods_ircc)

    out.write("call and-or tree:\n")
    pp = pprint.PrettyPrinter(indent=4, stream=out)
    pp.pprint(call_tree)

if __name__ == '__main__':
    main(sys.argv)
