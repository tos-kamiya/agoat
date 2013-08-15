#coding: utf-8

import sys
from itertools import groupby

from _utilities import sort_uniq

import jimp_parser as jp
import jimp_code_parser as jcp
from andor_tree import ORDERED_AND, ORDERED_OR, normalize_tree

# SPECIALINVOKE = "specialinvoke"
    #receiver, method_name, args, retv
# INVOKE = "invoke"
    #receiver, method_name, args, retv

# RETURN = "return"
# THROW = "throw"
# IFGOTO = "ifgoto"
# GOTO = "goto"
# SWITCH = "switch"
# LABEL = "label"

def resolve_type(inss, method_data, class_data):
    def resolve(name):
        if name is None:
            return None
        if name in ("true", "false"):
            return 'boolean'
        elif name.startswith("'"):
            return "char"
        elif name.startswith('"'):
            return "java.lang.String"
        elif name[0] in "-+0123456789":
            s = name[-1]
            if s == 'L':
                return 'long'
            elif s == 'F':
                return 'float'
            elif s == 'D':
                return 'double'
            else:
                return 'int'
        return method_data.fields.get(name) or class_data.fields.get(name)
    
    resolved_inss = []
    for ins in inss:
        cmd = ins[0]
        if cmd in (jcp.SPECIALINVOKE, jcp.INVOKE):
            receiver, method_name, args, retv, linenum = ins[1:]
            rreceiver = resolve(receiver)
            rargs = tuple(map(resolve, args))
            rretv = resolve(retv)
            sig = jp.MethodSig(rretv, method_name, rargs)
            resolved_inss.append((cmd, rreceiver, sig, linenum))
        else:
            resolved_inss.append(ins)
    
    return resolved_inss

def convert_to_execution_paths(inss):
    len_inss = len(inss)
    label2dest = {}
    for i, ins in enumerate(inss):
        if ins[0] == jcp.LABEL:
            label2dest[ins[1]] = i

    paths = []
    path = []
    paths.append(path)
    branches = []
    branches.append((0, path, []))
    
    def dig(i, path, visitedlabels):
        while i < len_inss:
            ins = inss[i]
            cmd = ins[0]
            if cmd in (jcp.SPECIALINVOKE, jcp.INVOKE):
                path.append(ins)
            elif cmd in (jcp.RETURN, jcp.THROW):
                path.append(ins)
                return
            elif cmd == jcp.IFGOTO:
                dest = ins[1]
                path.append(ins)  # mark of branch/join
                if dest not in visitedlabels:
                    branched_path = path[:]
                    paths.append(branched_path)
                    branches.append((label2dest.get(dest), branched_path, visitedlabels[:]))
            elif cmd == jcp.GOTO:
                dest = ins[1]
                if dest in visitedlabels:
                    return
                visitedlabels.append(dest)
                i = label2dest.get(dest)
                continue
            elif cmd == jcp.SWITCH:
                path.append(ins)  # mark of branch/join
                for dest in ins[1]:
                    if dest not in visitedlabels:
                        branched_path = path[:]
                        paths.append(branched_path)
                        branches.append((label2dest.get(dest), branched_path, visitedlabels[:]))
                return
            elif cmd == jcp.LABEL:
                path.append(ins)  # mark of branch/join
            i += 1
    
    while branches:
        b = branches.pop()
        dig(*b)

    return sort_uniq(paths)

def paths_to_ordred_andor_tree(paths):
    def get_prefix(paths):
        assert paths
        prefix = []
        for items in zip(*paths):
            c = items[0]
            if any(i != c for i in items[1:]):
                break
            prefix.append(c)
        return prefix
    def get_postfix(paths):
        assert paths
        postfix = []
        for items in zip(*map(reversed, paths)):
            c = items[0]
            if any(i != c for i in items[1:]):
                break
            postfix.append(c)
        return list(reversed(postfix))

    if len(paths) == 0:
        return [ORDERED_AND]

    if len(paths) == 1:
        return [ORDERED_AND] + paths[0]

    emptyG, multipleG = [], []
    for p in paths:
        lenp = len(p)
        (emptyG if lenp == 0 else \
            multipleG).append(p)
    t = [ORDERED_OR]
    if emptyG:
        t.append([ORDERED_AND])
    multipleG = sort_uniq(multipleG)
    prefix_division = [list(g) for k, g in groupby(multipleG, key=lambda p: p[0])]
    postfix_division = [list(g) for k, g in groupby(multipleG, key=lambda p: p[-1])]
    if len(prefix_division) <= len(postfix_division):
        for g in prefix_division:
            if len(g) == 1:
                t.append([ORDERED_AND] + g[0])
            else:
                prefix = get_prefix(g)
                pt = [ORDERED_AND]
                t.append(pt)
                pt.extend(prefix)
                len_prefix = len(prefix)
                tails = [p[len_prefix:] for p in g]
                pt.append(paths_to_ordred_andor_tree(tails))
    else:
        for g in postfix_division:
            if len(g) == 1:
                t.append([ORDERED_AND] + g[0])
            else:
                postfix = get_postfix(g)
                len_postfix = len(postfix)
                heads = [p[:-len_postfix] for p in g]
                pt = [ORDERED_AND]
                t.append(pt)
                pt.append(paths_to_ordred_andor_tree(heads))
                pt.extend(postfix)

    return normalize_tree(t)

def extract_class_hierarchy(class_table):
    class_to_descendants = {}  # str -> [str]
    for clz, class_data in class_table.iteritems():
        if class_data.base_name:
            class_to_descendants.set_default(class_data.base_name, []).append(clz)
    return class_to_descendants

def main(argv, out=sys.stdout):
    filename = argv[1]
    out.write("file: %s\n" % filename)
    lines = list(jp.readline_iter(filename))
    class_data_table = jp.parse_jimp_lines(lines)
    
    for clz, cd in class_data_table.iteritems():
        for method_sig, md in cd.methods.iteritems():
            inss = resolve_type(md.code, md, cd)
#             out.write("%s, %s:\n" % (clz, method_sig))
#             for ins in inss:
#                 out.write("  %s\n" % repr(ins))
            paths = convert_to_execution_paths(inss)
            out.write("%s, %s:\n" % (clz, method_sig))
            for pi, path in enumerate(paths):
                out.write("  path %d:\n" % pi)
                for ins in path:
                    out.write("    %s\n" % repr(ins))

if __name__ == '__main__':
    main(sys.argv)
