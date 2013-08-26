#coding: utf-8

try:
    from sys import intern  # py3k
except:
    pass

import sys
from itertools import groupby

from _utilities import sort_uniq

import jimp_parser as jp
from andxor_tree import ORDERED_AND, ORDERED_XOR, normalize_tree

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

MethodSigInternTable = dict()
def method_sig_intern(msig):
    v = MethodSigInternTable.get(msig)
    if v:
        return v
    MethodSigInternTable[msig] = msig
    return msig

def resolve_type(inss, method_data, class_data):
    if inss is None:
        assert False
    def resolve(name):
        if name is None:
            return None
        if name.startswith("class "):
            return 'java.lang.Class'
        elif name in ("true", "false"):
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
        t = method_data.fields.get(name)
        if t:
            return intern(t)
        t = class_data.fields.get(name)
        if t:
            return intern(t)
        return None
    
    resolved_inss = []
    for ins in inss:
        cmd = ins[0]
        if cmd in (jp.SPECIALINVOKE, jp.INVOKE):
            receiver, method_name, args, retv, linenum = ins[1:]
            rreceiver = resolve(receiver)
            rargs = tuple(map(resolve, args))
            rretv = resolve(retv)
            sig = method_sig_intern(jp.MethodSig(rretv, method_name, rargs))
            resolved_inss.append((cmd, rreceiver, sig, linenum))
        else:
            resolved_inss.append(ins)
    
    return resolved_inss

def convert_to_execution_paths(inss):
    len_inss = len(inss)
    label2dest = {}
    for i, ins in enumerate(inss):
        if ins[0] == jp.LABEL:
            label2dest[ins[1]] = i

    def gen_subrange_paths():
        def widen_flow(flow_widths, beg, end):
            if beg > end:
                tmp = beg; beg = end; end = tmp
            for j in range(beg, end + 1):
                flow_widths[j] = True
    
        flow_widths = [False] * len_inss
        for i, ins in enumerate(inss):
            ins = inss[i]
            cmd = ins[0]
            if cmd == jp.IFGOTO:
                dest = ins[1]
                dest_index = label2dest.get(dest)
                widen_flow(flow_widths, i, dest_index)
            elif cmd == jp.GOTO:
                dest = ins[1]
                dest_index = label2dest.get(dest)
                widen_flow(flow_widths, i, dest_index)
            elif cmd == jp.SWITCH:
                # path.append(ins)  # mark of branch/join
                for dest in ins[1]:
                    dest_index = label2dest.get(dest)
                    widen_flow(flow_widths, i, dest_index)
        
        ins_ranges = []
        cur_width = None
        cur_start = 0
        for i in range(0, len_inss):
            prev_width = cur_width
            cur_width = flow_widths[i]
            if prev_width is None:
                prev_width = cur_width
            if cur_width != prev_width:
                ins_ranges.append((cur_start, i))
                cur_start = i
        ins_ranges.append((cur_start, len_inss))
    
        return ins_ranges
    
    def dig_subrange_paths(beg, end):
        paths = []
        path = []
        paths.append(path)
        branches = []
        branches.append((beg, path, []))
        
        def dig(i, path, visitedlabels):
            while i < end:
                ins = inss[i]
                cmd = ins[0]
                if cmd in (jp.SPECIALINVOKE, jp.INVOKE):
                    is_repetitive = path and path[-1][:-1] == ins[:-1]
                    # cmd, receiver, method_name, args, retv, linenum = ins
                    if not is_repetitive:
                        path.append(ins)
                        if len(path) > end - beg:
                            assert False
                        assert len(path) <= end - beg
                elif cmd in (jp.RETURN, jp.THROW):
                    path.append(ins)
                    return
                elif cmd == jp.IFGOTO:
                    dest = ins[1]
                    # path.append(ins)  # mark of branch/join
                    if dest not in visitedlabels:
                        branched_path = path[:]
                        paths.append(branched_path)
                        branches.append((label2dest.get(dest), branched_path, visitedlabels[:] + [dest]))
                elif cmd == jp.GOTO:
                    dest = ins[1]
                    if dest in visitedlabels:
                        return
                    visitedlabels.append(dest)
                    i = label2dest.get(dest)
                    continue
                elif cmd == jp.SWITCH:
                    # path.append(ins)  # mark of branch/join
                    for dest in ins[1]:
                        if dest not in visitedlabels:
                            branched_path = path[:]
                            paths.append(branched_path)
                            branches.append((label2dest.get(dest), branched_path, visitedlabels[:] + [dest]))
                    return
                elif cmd == jp.LABEL:
                    visitedlabels.append(ins[1])
                    path.append(ins)  # mark of branch/join
                i += 1
        
        while branches:
            b = branches.pop()
            dig(*b)
    
        return sort_uniq(paths)

    ins_ranges = gen_subrange_paths()
    rangedpaths_seq = [dig_subrange_paths(*ir) for ir in ins_ranges]
    return rangedpaths_seq

def rangedpaths_to_ordred_andxor_tree(paths):
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
    t = [ORDERED_XOR]
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
                pt.append(rangedpaths_to_ordred_andxor_tree(tails))
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
                pt.append(rangedpaths_to_ordred_andxor_tree(heads))
                pt.extend(postfix)

    return normalize_tree(t)

def paths_to_ordred_andxor_tree(rangedpaths_seq):
    if len(rangedpaths_seq) == 1:
        return rangedpaths_to_ordred_andxor_tree(rangedpaths_seq[0])

    t0 = t = [ORDERED_AND]
    for paths in rangedpaths_seq:
        terminted = []
        continuing = []
        for p in paths:
            if p and p[-1][0] in (jp.RETURN, jp.THROW):
                terminted.append(p)
            else:
                continuing.append(p)
        if not continuing:
            assert terminted
            t.append(rangedpaths_to_ordred_andxor_tree(terminted))
            return t0

        if terminted:
            n1 = [ORDERED_XOR]
            t.append(n1)
            n1.append(rangedpaths_to_ordred_andxor_tree(terminted))
            n2 = [ORDERED_AND]
            t.append(n2)
            n2.append(rangedpaths_to_ordred_andxor_tree(continuing))
            t = n2
        else:
            t.append(rangedpaths_to_ordred_andxor_tree(continuing))

    return t0

def replace_method_code_with_axt_in_class_table(class_table, progress_repo=None):
    for cd in class_table.itervalues():
        for md in cd.methods.itervalues():
            progress_repo and progress_repo(cd.class_name, md.method_sig)
            inss = resolve_type(md.code, md, cd)
            paths = convert_to_execution_paths(inss)
            axt = paths_to_ordred_andxor_tree(paths)
            md.code = axt

def main(argv, out=sys.stdout):
    filename = argv[1]
    out.write("file: %s\n" % filename)
    lines = list(jp.readline_iter(filename))
    r = jp.parse_jimp_lines(lines)
    if r is None:
        out.write("contains no class\n")
        return
    
    clz, cd = r
    for method_sig, md in cd.methods.iteritems():
        inss = resolve_type(md.code, md, cd)
#         out.write("%s, %s:\n" % (clz, method_sig))
#         for ins in inss:
#             out.write("  %s\n" % repr(ins))
        paths = convert_to_execution_paths(inss)
#         out.write("%s, %s:\n" % (clz, method_sig))
#         for pi, path in enumerate(paths):
#             out.write("  path %d:\n" % pi)
#             for ins in path:
#                 out.write("    %s\n" % repr(ins))
        axt = paths_to_ordred_andxor_tree(paths)
        out.write("%s, %s:\n" % (clz, method_sig))
        out.write("%s\n" % repr(axt))

if __name__ == '__main__':
    main(sys.argv)
