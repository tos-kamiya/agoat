# coding: utf-8

import sys
import collections

import _utilities
import jimp_parser as jp
import _jimp_code_body_to_tree_elem as jcbte
import calltree as ct
from _jimp_code_body_to_tree_elem import inss_to_tree, inss_to_tree_in_class_table  # re-export


def callnode_label(call_node):
    node_label = (call_node.invoked.callee, call_node.recursive_cxt)
    return node_label


def extract_class_hierarchy(class_table, include_indirect_decendants=True):
    # class_table  # str -> ClassData
    class_to_descendants = collections.defaultdict(dict)  # str -> str -> int, that is, clz -> descendant_clz -> distance
    for clz, class_data in class_table.iteritems():
        if class_data.base_name:
            class_to_descendants[class_data.base_name][clz] = 1
        if class_data.interf_names:
            for interf in class_data.interf_names:
                class_to_descendants[interf][clz] = 1

    if include_indirect_decendants:
        while True:
            added_dds = []
            for clz, d_depths in class_to_descendants.iteritems():
                for d, d_dep in d_depths.iteritems():
                    for dd, dd_dep in class_to_descendants.get(d, {}).iteritems():
                        if dd not in d_depths:
                            added_dds.append((clz, dd, d_dep + dd_dep))
            if not added_dds:
                break  # while True
            for clz, dd, dd_dep in added_dds:
                class_to_descendants[clz][dd] = dd_dep

    return class_to_descendants

# def interface_implementation_table(class_table):
# iterface_to_classes = {}  # str -> [str]
#     for clz, class_data in class_table.iteritems():
#         if class_data.interf_names:
#             for i in class_data.interf_names:
#                 iterface_to_classes.setdefault(i, []).add(clz)
#     return iterface_to_classes


def clzmsig_mnamc(msig):
    return jp.clzmsig_method(msig), len(jp.clzmsig_params(msig))


def make_dispatch_table(class_to_methods, class_to_descendants):
    # class_to_descendants  # str -> str -> int
    # class_to_methods  # str -> [ClzMethodSig]

    recv_method_to_defs = {}  # recv_method_to_defs  # (clz, mnamc) -> [ClzMethodSig]

    # expand towards descendants
    # Overriding methods (child class's methods) are possible to be dispatched
    # in case of parent class's method call.
    for clz_mtds in class_to_methods.iteritems():
        clz, clzmsigs = clz_mtds
        mnamcs = _utilities.sort_uniq([clzmsig_mnamc(clzmsig) for clzmsig in clzmsigs])
        assert clz

        cands = [clz]  # clz and its all descendant classes
        descends = class_to_descendants.get(clz)
        if descends:
            cands.extend(descends.keys())

        for d in cands:
            for mnamc in mnamcs:
                for dclzmsig in class_to_methods.get(d, []):
                    if clzmsig_mnamc(dclzmsig) == mnamc:
                        recv_method_to_defs.setdefault((clz, mnamc), []).append(dclzmsig)

    # expand towards ascendants
    # When methods are defined in a class but not in its child class,
    # such methods are possible to be dispatched in case of child class's method call
    depth = 0
    max_depth = 1
    while depth < max_depth:
        depth += 1
        for clz, d_deps in class_to_descendants.iteritems():
            for des, d in d_deps.iteritems():
                if d != depth: 
                    if d > max_depth:
                        max_depth = d  # found deeper inheritance
                    continue  # for des, d
                clz_clzmsigs = class_to_methods.get(clz, [])
                if not clz_clzmsigs: continue  # for des, d
                des_clzmsigs = set(class_to_methods.get(des, []))
                des_msigs = map(jp.clzmsig_methodsig, des_clzmsigs)
                for clz_clzmsig in clz_clzmsigs:
                    clz_msig = jp.clzmsig_methodsig(clz_clzmsig)
                    if clz_msig not in des_msigs:  # if method defined in clz but not in des
                        recv_method_to_defs.setdefault((des, clzmsig_mnamc(clz_clzmsig)), []).append(clz_clzmsig)

    for cms in recv_method_to_defs.itervalues():
        cms.sort()
    return recv_method_to_defs


def java_is_a(type_a, type_b, class_to_descendants):
    if type_a is None or type_b is None:  # Java's void type
        return 0 if type_a == type_b else -1
    if type_a == 'null':
        if type_b in ('byte', 'short', 'int', 'long', 'boolean', 'char', 'float', 'double'):
            return -1
        else:
            return 0
    while type_a.endswith('[]'):
        if not type_b.endswith('[]'):
            return -1
        type_a = type_a[:-2]
        type_b = type_b[:-2]
    if type_a == type_b:
        return 0
    des2dis = class_to_descendants.get(type_b, {})
    dis = des2dis.get(type_a)
    return dis if dis is not None else -1


def gen_method_dispatch_resolver(class_table, class_to_descendants, recv_method_to_defs):
    # class_table  # str -> ClassData
    # recv_method_to_defs  # recv_method_to_defs  # (clz, mnamc) -> [ClzMethodSig]
    def resolve_dispatch(invoke_cmd, clzmsig):
        static_method = invoke_cmd == jp.SPECIALINVOKE
        resolved = []
        recv = jp.clzmsig_clz(clzmsig)
        mnamc = clzmsig_mnamc(clzmsig)
        cands = recv_method_to_defs.get((recv, mnamc))
        if cands is None:
            return resolved
        for cclzmsig in cands:
            cclz = jp.clzmsig_clz(cclzmsig)
            if static_method and cclz != recv:
                continue  # cclz, cmsig
            unmatch = False
            total_distance = 0
            for p, cp in zip(jp.clzmsig_params(clzmsig), jp.clzmsig_params(cclzmsig)):
                d = java_is_a(p, cp, class_to_descendants)
                if d < 0:
                    unmatch = True
                    break  # for p, cp
                total_distance += d
            if unmatch:
                continue  # cclz, cmsig
            retv, cretv = jp.clzmsig_retv(clzmsig), jp.clzmsig_retv(cclzmsig)
            d = java_is_a(cretv, retv, class_to_descendants)
            if d < 0:
                continue  # cclz, cmsig 
            total_distance += d

            # TODO: Narrow down with inheritance hierachy
            # e.g. if two methods "void someMethod(Object)" and "void someMethod(String)" exist,
            # a method call someMethod("abc") is resolved the latter, not the former.
            # The current implementation returns both ones as possible dispatches.

            cd = class_table.get(cclz)
            if cd:
                md = cd.methods.get(cclzmsig)
                if md:
                    resolved.append(md)
        return resolved
    return resolve_dispatch


def find_methods_involved_in_recursive_call_chain(entry_point, resolve_dispatch,
          include_direct_recursive_calls=False):
    # entry_points  # list of ClzMethodSig

    methods_searched = set()
    # set of ClzMethodSig # methods involved in recursive call chain
    methods_ircc = set()

    cmzmsig0 = entry_point
    e = resolve_dispatch(jp.SPECIALINVOKE, entry_point)
    if not e:
        raise ValueError("entry_point not found")
    md0 = e[0]
    aot = md0.code if md0 else None
    if aot is None:
        raise ValueError("entry_point not found")

    def dig_node(node, stack):
        len_stack0 = len(stack)
        try:
            if isinstance(node, tuple):
                assert node
                cmd = node[0]
                if cmd in (jp.SPECIALINVOKE, jp.INVOKE):
                    called_clzmsig = node[1]
                    if not include_direct_recursive_calls and called_clzmsig == stack[-1]:
                        pass
                    else:
                        r = resolve_dispatch(cmd, called_clzmsig)
                        for md in r:
                            dig_call(md, stack)
                elif cmd in (jp.LABEL, jp.RETURN, jp.THROW):
                    pass
                else:
                    # sys.stderr.write("node = %s\n" % repr(node))
                    assert False
            elif isinstance(node, list):
                assert node
                assert node[0] in (jcbte.ORDERED_AND, jcbte.ORDERED_OR)
                for item in node[1:]:
                    dig_node(item, stack)
        finally:
            if len(stack) > len_stack0:
                stack[:] = stack[:len_stack0]

    def dig_call(md, stack):
        clzmsig = md.clzmsig
        len_stack0 = len(stack)
        try:
            aot = md.code
            if not aot:
                return
            try:
                i = stack.index(clzmsig)
                methods_ircc.update(stack[i:])
                return
            except:
                pass
            if clzmsig in methods_searched:
                return
            methods_searched.add(clzmsig)
            stack.append(clzmsig)
            dig_node(aot, stack)
        finally:
            if len(stack) > len_stack0:
                stack[:] = stack[:len_stack0]

    stack_sentinel = None
    dig_call(md0, [stack_sentinel])

    s = list(methods_ircc)
    s.sort()
    return s


def find_entry_points(class_table, target_class_names=None):
    # class_table  # str -> ClassData
    entrypoint_retv_method_params = set([
        (None, "main", ("java.lang.String[]",)), 
        (None, "run", ()),
        (None, "<clinit>", ())
    ])
    entry_points = []

    if target_class_names is None:
        target_class_names = class_table.iterkeys()
    for clz in target_class_names:
        class_data = class_table.get(clz)
        if not class_data: continue
        for clzmsig in class_data.methods.iterkeys():
            rmp = (jp.clzmsig_retv(clzmsig), jp.clzmsig_method(clzmsig), jp.clzmsig_params(clzmsig))
            if rmp in entrypoint_retv_method_params:
                entry_points.append(clzmsig)
    return entry_points


def build_call_andor_tree(entry_point, resolve_dispatch, methods_ircc, call_node_memo={}):
    # entry_point  # ClzMethodSig
    # methods_ircc  # set of ClzMethodSig
    # call_node_memo = {}  # (ClzMethodSig, recursive_context) -> node

    def dig_node(aot, recursive_context, clzmsig):
        if isinstance(aot, list):
            assert aot
            aot0 = aot[0]
            if aot0 in (ct.ORDERED_AND, ct.ORDERED_OR, jcbte.BLOCK):
                has_empty_subs = False
                n = [aot0]
                for item in aot[1:]:
                    v = dig_node(item, recursive_context, clzmsig)
                    if v is None:
                        has_empty_subs = True
                    else:
                        n.append(v)
                if aot0 == ct.ORDERED_OR and has_empty_subs:
                    n.insert(1, [ct.ORDERED_AND])
                len_n = len(n)
                if len_n == 2:
                    return n[1]
                elif len_n == 1:
                    return None
                return n
            else:
                assert False
        elif isinstance(aot, tuple):
            assert aot
            cmd = aot[0]
            if cmd in (jp.SPECIALINVOKE, jp.INVOKE):
                recv_clzmsig = aot[1]
                if recv_clzmsig == clzmsig or recv_clzmsig == recursive_context:
                    return None
                loc_info = '\n'.join([clzmsig, "%d" % aot[3]])
                v = dig_dispatch(cmd, recv_clzmsig, recursive_context, aot[2], loc_info)
                if v: 
                    return v
                return ct.Invoked(cmd, recv_clzmsig, aot[2], loc_info)
            else:
                return None
        else:
            return None

    digging_calls = []
    def dig_dispatch(cmd, recv_clzmsig, recursive_context, literals, loc_info):
        cand_methods = resolve_dispatch(cmd, recv_clzmsig)
        if not cand_methods:
            return ct.Invoked(cmd, recv_clzmsig, literals, loc_info)
        dispatch_node = [ct.ORDERED_OR]
        for md in cand_methods:
            clzmsig = md.clzmsig
            rc = recursive_context
            if clzmsig in digging_calls:
                # a recursive call is always a leaf node
                dispatch_node.append(ct.Invoked(cmd, clzmsig, literals, loc_info))
            else:
                if rc is None and clzmsig in methods_ircc:
                    rc = clzmsig
                invoked = ct.Invoked(cmd, clzmsig, literals, loc_info)
                node_label = callnode_label(ct.CallNode(invoked, rc, None))
                v = call_node_memo.get(node_label)
                if v is None:
                    assert clzmsig not in digging_calls  # assert this call is not a recursive one
                    digging_calls.append(clzmsig)
                    v = dig_node(md.code, rc, clzmsig)
                    digging_calls.pop()
                    call_node_memo[node_label] = v
                cn = ct.CallNode(invoked, rc, v)
                dispatch_node.append(cn)
        len_dispatch_node = len(dispatch_node)
        if len_dispatch_node == 1:
            return None
        elif len_dispatch_node == 2:
            return dispatch_node[1]
        else:
            return dispatch_node

    return dig_dispatch(jp.SPECIALINVOKE, entry_point, None, (), None)


def extract_call_andor_trees(class_table, entry_points):
    class_to_descendants = extract_class_hierarchy(class_table)
    class_to_methods = dict((claz, cd.methods.keys()) for claz, cd in class_table.iteritems())
    # class_to_methods  # str -> [ClzMethodSig]

    recv_method_to_defs = make_dispatch_table(class_to_methods, class_to_descendants)

    resolve_dispatch = gen_method_dispatch_resolver(class_table, class_to_descendants, recv_method_to_defs)

    methods_ircc = set()
    for entry_point in entry_points:
        ms = find_methods_involved_in_recursive_call_chain(entry_point, resolve_dispatch)
        methods_ircc.update(ms)
    methods_ircc = sorted(methods_ircc)
    # out.write("methods involved in recursive chain:\n")
    # for mtd in methods_ircc:
    #     out.write("  %s\n" % repr(mtd))

    call_trees = []
    call_node_memo = {}
    for entry_point in entry_points:
        call_tree = build_call_andor_tree(entry_point, resolve_dispatch, methods_ircc, call_node_memo=call_node_memo)
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
        entry_point = None
        for cd in class_table.itervalues():
            if entry_point:
                break  # for cd
            if cd.class_name == entry_point_class:
                for md in cd.methods.itervalues():
                    if entry_point:
                        break  # for md
                    if jp.clzmsig_method(md.clzmsig).find(entry_point_method) >= 0:
                        entry_point = md.clzmsig
    else:
        entry_point = jp.ClzMethodSig(entry_point_class, None, "main", ("java.lang.String[]",))
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
    # class_to_methods  # str -> [ClzMethodSig]

    recv_method_to_defs = make_dispatch_table(
        class_to_methods, class_to_descendants)

    logout and logout.write("> find recursive\n")
    resolver = gen_method_dispatch_resolver(class_table, class_to_descendants, recv_method_to_defs)
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
