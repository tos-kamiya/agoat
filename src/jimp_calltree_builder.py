#coding: utf-8

import os
import sys

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
    methods_ircc = set()  # methods involved in recursive call chain

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
                    sys.stderr.write("node = %s\n" % repr(node))
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
    entry_points = []
    for clz, class_data in class_table.iteritems():
        for msig, method_data in class_data.methods.iteritems():
            if msig.retv is None and msig.name == "main" and msig.params == ("java.lang.String[]",):
                entry_points.append((clz, msig))
    return entry_points

def main(argv, out=sys.stdout):
    dirname = argv[1]
    entry_point_class = argv[2] if len(argv) >= 3 else None
    
    out.write("sootOutput-dir: %s\n" % dirname)
    class_table = {}
    for clz, cd in jp.read_class_table_from_dir_iter(dirname):
        # sys.stderr.write("> %s\n" % clz)
        class_table[clz] = cd

    if not entry_point_class:
        entry_points = find_entry_points(class_table)
        out.write("entry points:\n")
        for ep in entry_points:
            out.write("  %s\n" % repr(ep))
        return

    jct.replace_method_code_with_axt_in_class_table(class_table)

    entry_point = (entry_point_class, jp.MethodSig(None, "main", ("java.lang.String[]",)))
    class_to_descendants = extract_class_hierarchy(class_table)
    class_to_methods = dict((claz, cd.methods.keys()) for claz, cd in class_table.iteritems())
    # class_to_methods  # str -> [MethodSig]
    recv_method_to_defs = resolve_dispatch(class_to_methods, class_to_descendants)
    methods_ircc = find_methods_involved_in_recursive_call_chain(class_table, recv_method_to_defs, entry_point)
    out.write("methods involved in recursive chain:\n")
    for mtd in methods_ircc:
        out.write("  %s\n" % repr(mtd))

if __name__ == '__main__':
    main(sys.argv)

