#coding: utf-8

import sys
import pprint

import andxor_tree as at
import jimp_parser as jp
import jimp_code_transformer as jct

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
#     iterface_to_classes = {}  # str -> [str]
#     for clz, class_data in class_table.iteritems():
#         if class_data.interf_names:
#             for i in class_data.interf_names:
#                 iterface_to_classes.setdefault(i, []).add(clz)
#     return iterface_to_classes

def resolve_dispatch(class_to_methods, class_to_descendants, iterface_to_classes=None):
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

# def generate_call_andor_tree(class_table, method_table, recv_method_to_defs, entry_point):
#     # class_table  # str -> ClassData
#     # method_table  # (str, MethodSig) -> axt
#     # recv_method_to_defs  # (str, MethodSig) -> [str]
#     # entry_point  # (str, MethodSig)
#     pass

def find_methods_involved_in_recursive_call_chain(class_table, recv_method_to_defs, entry_point,
        include_direct_recursive_calls=False):
    # class_table  # str -> ClassData
    # recv_method_to_defs  # (str, MethodSig) -> [str]
    # entry_point  # (str, MethodSig)
    
    methods_searched = set()
    methods_ircc = set()  # set of (str, MethodSig) # methods involved in recursive call chain

    clz0, mtd0 = entry_point
    cd = class_table.get(clz0)
    md = cd.methods.get(mtd0) if cd else None
    axt = md.code if md else None
    if axt is None:
        raise ValueError("entry_point not found")

    def dig_node(node, callee, stack):
        len_stack0 = len(stack)
        try:
            if isinstance(node, tuple):
                assert node
                cmd = node[0]
                if cmd == jp.SPECIALINVOKE:
                    rc_mtd = receiver_class, mtd = node[1], node[2]
                    if not include_direct_recursive_calls and rc_mtd == stack[-1]:
                        return
                    dig_call(receiver_class, mtd, stack)
                elif cmd == jp.INVOKE:
                    receiver, mtd = node[1], node[2]
                    for receiver_class in recv_method_to_defs.get((receiver, mtd), []):
                        rc_mtd = (receiver_class, mtd)
                        if not include_direct_recursive_calls and rc_mtd == stack[-1]:
                            return
                        dig_call(receiver_class, mtd, stack)
                else:
                    # sys.stderr.write("node = %s\n" % repr(node))
                    assert False
            elif isinstance(node, list):
                assert node
                assert node[0] in (jct.ORDERED_AND, jct.ORDERED_XOR)
                for item in node[1:]:
                    dig_node(item, callee, stack)
        finally:
            if len(stack) > len_stack0:
                stack[:] = stack[len_stack0:]

    def dig_call(clz, mtd, stack):
        len_stack0 = len(stack)
        try:
            cd = class_table.get(clz)
            if not cd:
                return
            md = cd.methods.get(mtd)
            if not md:
                return
            axt = md.code
            if not axt:
                return
            callee = (clz, mtd)
            try:
                i = stack.index(callee)
                methods_ircc.update(stack[i:])
                return
            except:
                pass
            if callee in methods_searched:
                return
            methods_searched.add(callee)
            stack.append(callee)
            node = axt[0]
            dig_node(node, callee, stack)
        finally:
            if len(stack) > len_stack0:
                stack[:] = stack[len_stack0:]
    
    stack_sentinel = None
    dig_call(clz0, mtd0, [stack_sentinel])
    
    s = list(methods_ircc)
    s.sort()
    return s

def find_entry_points(class_table):
    # class_table  # str -> ClassData
    main_msig = jp.MethodSig(None, "main", ("java.lang.String[]",))
    entry_points = []
    for clz, class_data in class_table.iteritems():
        for msig, method_data in class_data.methods.iteritems():
            if msig == main_msig:
                entry_points.append((clz, msig))
    return entry_points

CALL = "call"

def build_call_andxor_tree(entry_point, class_table, recv_method_to_defs, methods_ircc):
    # class_table  # str -> ClassData
    # recv_method_to_defs  # (str, MethodSig) -> [str]
    # entry_point  # (str, MethodSig)
    # methods_ircc  # set of (str, MethodSig)
    
    called_to_node_table = {}  # (str, MethodSig, recursive_context) -> node
    
    def dig_node(axt, recursive_context, clz_msig):
        if isinstance(axt, list):
            assert axt
            axt0 = axt[0]
            if axt0 in (at.ORDERED_AND, at.ORDERED_XOR, jct.BLOCK):
                n = [axt0]
                for item in axt[1:]:
                    v = dig_node(item, recursive_context, clz_msig)
                    if v is not None:
                        n.append(v)
                if len(n) == 2:
                    return n[1]
                return n
            else:
                assert False
        elif isinstance(axt, tuple):
            assert axt
            cmd = axt[0]
            if cmd == jp.SPECIALINVOKE:
                recv_msig = tuple(axt[1:3])
                if recv_msig == clz_msig or recv_msig == recursive_context:
                    return None
                loc_info = clz_msig, axt[3]
                v = dig_dispatch(recv_msig, recursive_context, loc_info, special_invoke=True)
            elif cmd == jp.INVOKE:
                recv_msig = tuple(axt[1:3])
                if recv_msig == clz_msig or recv_msig == recursive_context:
                    return None
                loc_info = clz_msig, axt[3]
                v = dig_dispatch(recv_msig, recursive_context, loc_info)
            else:
                return None
                # loc_info = clz_msig, axt[-1]
                # return tuple(list(axt[:-1]) + [loc_info])
            if not v:
                loc_info = clz_msig, axt[-1]
                return tuple(list(axt[:-1]) + [loc_info])
            return v
        else:
            return None
        
    def dig_dispatch(recv_msig, recursive_context, loc_info, special_invoke=False):
        recv, msig = recv_msig
        cands = [recv] if special_invoke else recv_method_to_defs.get(recv_msig, [])
        if not cands:
            return None
        dispatch_node = [at.ORDERED_XOR]
        for clz in cands:
            cd = class_table.get(clz)
            if cd:
                md = cd.methods.get(msig)
                if md:
                    called_method = cd.class_name, md.method_sig
                    ctx = called_method if recursive_context is None and called_method in methods_ircc else recursive_context
                    cn = called_to_node_table.get((cd.class_name, md.method_sig, ctx))
                    if cn is None:
                        cn = [CALL, (jp.INVOKE, called_method, loc_info)]
                        v = dig_node(md.code, ctx, called_method)
                        if v:
                            cn.append(v)
                        called_to_node_table[(cd.class_name, md.method_sig, ctx)] = cn
                    dispatch_node.append(cn)
        len_dispatch_node = len(dispatch_node)
        if len_dispatch_node == 1:
            return None
        elif len_dispatch_node == 2:
            return dispatch_node[1]
        else:
            return dispatch_node

    return dig_dispatch(entry_point, None, None, special_invoke=False)

def extract_call_andxor_tree(class_table, entry_point):
    class_to_descendants = extract_class_hierarchy(class_table)
    class_to_methods = dict((claz, cd.methods.keys()) for claz, cd in class_table.iteritems())
    # class_to_methods  # str -> [MethodSig]
    recv_method_to_defs = resolve_dispatch(class_to_methods, class_to_descendants)

    methods_ircc = find_methods_involved_in_recursive_call_chain(class_table, recv_method_to_defs, entry_point)
    # out.write("methods involved in recursive chain:\n")
    # for mtd in methods_ircc:
    #     out.write("  %s\n" % repr(mtd))

    call_tree = build_call_andxor_tree(entry_point, class_table, recv_method_to_defs, methods_ircc)
    return call_tree

def main(argv, out=sys.stdout, logout=sys.stderr):
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
                    if md.method_sig.name == entry_point_method:
                        entry_point_msig = md.method_sig
    else:
        entry_point_msig = jp.MethodSig(None, "main", ("java.lang.String[]",))
    entry_point = (entry_point_class, entry_point_msig)
    logout and logout.write("> entry point is: %s %s\n" % entry_point)

    logout and logout.write("> build axt\n")
    def progress_repo(clz, msig):
        sys.stderr.write(">   processing: %s %s\n" % (clz, msig))
    jct.replace_method_code_with_axt_in_class_table(class_table, progress_repo)

    logout and logout.write("> extract hierachy\n")
    class_to_descendants = extract_class_hierarchy(class_table)
    logout and logout.write("> reslove dispatch\n")
    class_to_methods = dict((claz, cd.methods.keys()) for claz, cd in class_table.iteritems())
    # class_to_methods  # str -> [MethodSig]
    recv_method_to_defs = resolve_dispatch(class_to_methods, class_to_descendants)

    logout and logout.write("> find recursive\n")
    methods_ircc = find_methods_involved_in_recursive_call_chain(class_table, recv_method_to_defs, entry_point)
    # out.write("methods involved in recursive chain:\n")
    # for mtd in methods_ircc:
    #     out.write("  %s\n" % repr(mtd))

    logout and logout.write("> build call and-xor tree\n")
    call_tree = build_call_andxor_tree(entry_point, class_table, recv_method_to_defs, methods_ircc)
    out.write("call and-xor tree:\n")
    pp = pprint.PrettyPrinter(indent=4, stream=out)
    pp.pprint(call_tree)

if __name__ == '__main__':
    main(sys.argv)

