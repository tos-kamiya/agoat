#coding: utf-8

try:
    from sys import intern  # py3k
except:
    pass

import sys
from itertools import groupby

from _utilities import sort_uniq, list_flatten_iter

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

if False:
    MethodSigInternTable = dict()
    def method_sig_intern(msig):
        v = MethodSigInternTable.get(msig)
        if v:
            return v
        MethodSigInternTable[msig] = msig
        return msig
else:
    def method_sig_intern(msig):
        return intern(msig)

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
            rreceiver = resolve(receiver) or receiver
            rargs = tuple(map(resolve, args))
            rretv = resolve(retv)
            sig = method_sig_intern(jp.MethodSig(rretv, method_name, rargs))
            resolved_inss.append((cmd, rreceiver, sig, linenum))
        else:
            resolved_inss.append(ins)
    
    return resolved_inss

BLOCK = 'block'

def convert_to_block_instruction_seq(inss):
    bis = []
    cur_block = None
    for i, ins in enumerate(inss):
        cmd = ins[0]
        if cmd in (jp.SPECIALINVOKE, jp.INVOKE):
            if cur_block is None:
                cur_block = [BLOCK]
            cur_block.append(ins)
        elif cmd in (jp.RETURN, jp.THROW, jp.IFGOTO, jp.GOTO, jp.SWITCH, jp.LABEL):
            if cur_block is not None:
                bis.append(cur_block)
                cur_block = None
            bis.append(ins)
        else:
            assert False
    return bis

def optimize_gotos_in_seq(inss):
    label2dest = {}
    for i, ins in enumerate(inss):
        if ins[0] == jp.LABEL:
            label2dest[ins[1]] = i
             
    def get_final_dest(label, visited_labels=set()):
        dest_label_index = label2dest.get(label)
        assert dest_label_index is not None
        dest_index = dest_label_index + 1
        ins = inss[dest_index]
        while ins[0] == jp.LABEL:
            lbl = ins[1]
            if lbl in visited_labels:
                break  # while
            label = label
            dest_index += 1
            ins = inss[dest_index]
        if ins[0]  == jp.GOTO:
            return get_final_dest(ins[1], visited_labels)
        return label
     
    def get_next_label(index):
        label = None
        dest_index = index + 1
        ins = inss[dest_index]
        while inss[dest_index][0] == jp.LABEL:
            label = ins[1]
            dest_index += 1
        ins = inss[dest_index]
        if ins[0] == jp.GOTO:
            return get_final_dest(ins[1])
        return label
 
    oinss = []
    for i, ins in enumerate(inss):
        cmd = ins[0]
        if cmd == jp.IFGOTO:
            dest = ins[1]
            fdest = get_final_dest(dest)
            fdest2 = get_next_label(i)
            if fdest2 == fdest:
                oinss.append((jp.GOTO, fdest))
            else:
                oinss.append((jp.IFGOTO, fdest))
        elif cmd == jp.SWITCH:
            dests = ins[1]
            fdests = [get_final_dest(d) for d in dests]
            fdests = sort_uniq(fdests)
            if len(fdests) == 1:
                oinss.append((jp.GOTO, fdests[0]))
            else:
                oinss.append((jp.SWITCH, fdests))
        else:
            oinss.append(ins)
    return oinss

def convert_to_execution_paths(inss):
    len_inss = len(inss)
    label2dest = {}
    for i, ins in enumerate(inss):
        if ins[0] == jp.LABEL:
            label2dest[ins[1]] = i

    paths = []
    path = []
    branches = []
    branches.append((0, path, []))
    
    def nesting_dup(L):
        if len(L) == 1:
            return [L[0]]
        else:
            return [L]
    def dig(i, path, visitedlabels):
        while i < len_inss:
            ins = inss[i]
            cmd = ins[0]
            if cmd == BLOCK:
                path.append(ins)
            elif cmd in (jp.SPECIALINVOKE, jp.INVOKE):
                is_repetitive = path and path[-1][:-1] == ins[:-1]
                # cmd, receiver, method_name, args, retv, linenum = ins
                if not is_repetitive:
                    path.append(ins)
                    assert len(path) <= len_inss
            elif cmd in (jp.RETURN, jp.THROW):
                path.append(ins)
                paths.append(path)
                return
            elif cmd == jp.IFGOTO:
                dest = ins[1]
                # path.append(ins)  # mark of branch/join
                if dest not in visitedlabels:
                    branched_path = nesting_dup(path)
                    path = nesting_dup(path)
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
                        branched_path = nesting_dup(path)
                        branches.append((label2dest.get(dest), branched_path, visitedlabels[:] + [dest]))
                return
            elif cmd == jp.LABEL:
                visitedlabels.append(ins[1])
                path.append(ins)  # mark of branch/join
            else:
                assert False
            i += 1
        paths.append(path)
    
    while branches:
        b = branches.pop()
        dig(*b)

    #  len_paths = len(paths)  # debug
    paths = sort_uniq(paths, key=lambda p: sum(map(hash, list_flatten_iter(p))))
    #  sys.stderr.write("removed path: %d\n" % (len_paths - len(paths)))  #debug
    paths = [list(list_flatten_iter(p)) for p in paths]
    paths.sort()
    return paths

def paths_to_ordred_andxor_tree(paths):
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
                pt.append(paths_to_ordred_andxor_tree(tails))
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
                pt.append(paths_to_ordred_andxor_tree(heads))
                pt.extend(postfix)

    return normalize_tree(t)

def replace_method_code_with_axt_in_class_table(class_table, progress_repo=None):
    for cd in class_table.itervalues():
        for md in cd.methods.itervalues():
            progress_repo and progress_repo(cd.class_name, md.method_sig)
            inss = resolve_type(md.code, md, cd)
            bis = convert_to_block_instruction_seq(inss)
            obis = optimize_gotos_in_seq(bis)
            paths = convert_to_execution_paths(obis)
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
        bis = convert_to_block_instruction_seq(inss)
        obis = optimize_gotos_in_seq(bis)
        paths = convert_to_execution_paths(obis)
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
