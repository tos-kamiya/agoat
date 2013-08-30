#coding: utf-8

try:
    from sys import intern  # py3k
except:
    pass

import sys
import pprint
from collections import Counter

from _utilities import sort_uniq
import jimp_parser as jp
import jimp_code_optimizer as jco
from andxor_tree import ORDERED_AND, ORDERED_XOR, normalize_tree
from _jimp_code_box_generator import BOX, BLOCK
import _jimp_code_box_generator

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
        if name == 'null':
            return 'java.lang.Object'  # unknown
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

def get_max_branches_of_boxes(inss):
    c = 0
    for i, ins in enumerate(inss):
        cmd = ins[0]
        if cmd in (jp.RETURN, jp.THROW, jp.IFGOTO):
            c += 1
        elif cmd == jp.SWITCH:
            c += len(ins[1])
    maxc = c
    for i, ins in enumerate(inss):
        cmd = ins[0]
        if cmd == BOX:
            subc = get_max_branches_of_boxes(ins[1:])
            maxc = max(c, subc)
    return maxc

def list_flatten_iter_except_for_block(L):
    if isinstance(L, list):
        if L and L[0] == BLOCK:
            yield L
        elif L and L[0] == BOX:
            yield L
        else:
            for li in L:
                for e in list_flatten_iter_except_for_block(li):
                    yield e
    else:
        yield L

def convert_to_execution_paths(inss):
    if inss and inss[0] == BLOCK:
        return inss

    len_inss = len(inss)
    label2index = _jimp_code_box_generator.get_label2index(inss)
 
    paths = []
    path = []
    branches = []
    branches.append((0, path, Counter()))
     
    def nesting_dup(L):
        if len(L) == 1:
            return [L[0]]
        else:
            return [L]
    def dig(i, path, visitedlabels):
        if i is None:
            assert False
        prev_i = i - 1
        while i < len_inss:
            assert i != prev_i
            prev_i = i
            ins = inss[i]
            cmd = ins[0]
            if cmd == BLOCK:
                path.append(ins)
            elif cmd == BOX:
                b = [BOX]
                b.extend(convert_to_execution_paths(ins[1:]))
                path.append(b)
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
                    path = nesting_dup(path)
                    branches.append((label2index[dest], nesting_dup(path), visitedlabels.copy()))
            elif cmd == jp.GOTO:
                dest = ins[1]
                dest_index = label2index.get(dest)
                if dest_index < i:
                    c = visitedlabels[dest]
                    if c >= 2:
                        return
                    visitedlabels[dest] += 1
                    i = dest_index + 1
                else:
                    i = dest_index
                continue
            elif cmd == jp.SWITCH:
                # path.append(ins)  # mark of branch/join
                for dest in ins[1]:
                    if dest not in visitedlabels:
                        branches.append((label2index[dest], nesting_dup(path), visitedlabels.copy()))
                return
            elif cmd == jp.LABEL:
                if ins[1] in visitedlabels:
                    return
                visitedlabels[ins[1]] += 1
                path.append(ins)  # mark of branch/join
            else:
                assert False
            i += 1
        if path:
            paths.append(path)
     
    while branches:
        b = branches.pop()
        dig(*b)
 
    paths = sort_uniq(paths)
    paths = [list(list_flatten_iter_except_for_block(p)) for p in paths]
    paths.sort()
    return paths

def paths_to_ordred_andxor_tree(paths):
    def ptoat_i(paths):
        if not paths:
            return [ORDERED_AND]
        t = [ORDERED_XOR]
        for p in paths:
            pt = [ORDERED_AND]
            for i in p:
                if isinstance(i, list):
                    assert i
                    if i[0] == BOX:
                        pt.append(ptoat_i(i[1:]))
                    else:
                        assert i[0] == BLOCK
                        pt.append(i)
                else:
                    pt.append(i)
            t.append(pt)
        return normalize_tree(t)
    return ptoat_i(paths)

# def paths_to_ordred_andxor_tree(paths):
#     def get_prefix(paths):
#         assert paths
#         prefix = []
#         for items in zip(*paths):
#             c = items[0]
#             if any(i != c for i in items[1:]):
#                 break
#             prefix.append(c)
#         return prefix
#     def get_postfix(paths):
#         assert paths
#         postfix = []
#         for items in zip(*map(reversed, paths)):
#             c = items[0]
#             if any(i != c for i in items[1:]):
#                 break
#             postfix.append(c)
#         return list(reversed(postfix))
#  
#     if len(paths) == 0:
#         return [ORDERED_AND]
#  
#     if len(paths) == 1:
#         return [ORDERED_AND] + paths[0]
#  
#     emptyG, multipleG = [], []
#     for p in paths:
#         lenp = len(p)
#         (emptyG if lenp == 0 else \
#             multipleG).append(p)
#     t = [ORDERED_XOR]
#     if emptyG:
#         t.append([ORDERED_AND])
#     multipleG = sort_uniq(multipleG)
#     prefix_division = [list(g) for k, g in groupby(multipleG, key=lambda p: p[0])]
#     postfix_division = [list(g) for k, g in groupby(multipleG, key=lambda p: p[-1])]
#     if len(prefix_division) <= len(postfix_division):
#         for g in prefix_division:
#             if len(g) == 1:
#                 t.append([ORDERED_AND] + g[0])
#             else:
#                 prefix = get_prefix(g)
#                 pt = [ORDERED_AND]
#                 t.append(pt)
#                 pt.extend(prefix)
#                 len_prefix = len(prefix)
#                 tails = [p[len_prefix:] for p in g]
#                 pt.append(paths_to_ordred_andxor_tree(tails))
#     else:
#         for g in postfix_division:
#             if len(g) == 1:
#                 t.append([ORDERED_AND] + g[0])
#             else:
#                 postfix = get_postfix(g)
#                 len_postfix = len(postfix)
#                 heads = [p[:-len_postfix] for p in g]
#                 pt = [ORDERED_AND]
#                 t.append(pt)
#                 pt.append(paths_to_ordred_andxor_tree(heads))
#                 pt.extend(postfix)
# 
#     return normalize_tree(t)

def expand_blocks(node):
    if not node:
        return node
    if isinstance(node, list):
        n0 = node[0]
        if n0 == BLOCK:
            subns = [expand_blocks(subn) for subn in node[1:]]
            if len(subns) == 1:
                return subns[0]
            else:
                return [ORDERED_AND] + subns
        elif n0 in (ORDERED_AND, ORDERED_XOR):
            subns = [expand_blocks(subn) for subn in node[1:]]
            return [n0] + subns
        else:
            assert False
    else:
        return node

NOTREE = 'notree'

def replace_method_code_with_axt_in_class_table(class_table, 
        branches_atmost=None, progress_repo=None):
    for cd in class_table.itervalues():
        for md in cd.methods.itervalues():
            progress_repo and progress_repo(current=(cd.class_name, md.method_sig))
            inss = resolve_type(md.code, md, cd)
            bis = _jimp_code_box_generator.make_block_and_box(inss)
            obis = jco.optimize_ins_seq(bis)
            nbranch = get_max_branches_of_boxes(obis)
            if branches_atmost is not None and nbranch > branches_atmost:
                progress_repo and progress_repo(canceled_becaseof_branches=(cd.class_name, md.method_sig, nbranch))
                md.code = [NOTREE, md.code]
            else:
                paths = convert_to_execution_paths(obis)
                axt = paths_to_ordred_andxor_tree(paths)
                axt = expand_blocks(axt)
                axt = normalize_tree(axt)
                md.code = axt

def main(argv, out=sys.stdout):
    filename = argv[1]
    out.write("file: %s\n" % filename)
    lines = list(jp.readline_iter(filename))
    r = jp.parse_jimp_lines(lines)
    if r is None:
        out.write("contains no class\n")
        return
    
    target_method_name_pattern = argv[2] if len(argv) >= 3 else None
    
    clz, cd = r
    for method_sig, md in cd.methods.iteritems():
        if target_method_name_pattern and jp.methodsig_name(method_sig).find(target_method_name_pattern) < 0:
            continue
        out.write("method: %s\n" % method_sig)
        inss = resolve_type(md.code, md, cd)
#         out.write("%s, %s:\n" % (clz, method_sig))
#         for ins in inss:
#             out.write("  %s\n" % repr(ins))
        bis = _jimp_code_box_generator.make_block_and_box(inss)
        obis = jco.optimize_ins_seq(bis)
        nbranch = get_max_branches_of_boxes(obis)
        out.write("branches: %d\n" % nbranch)
        paths = convert_to_execution_paths(obis)
        axt = paths_to_ordred_andxor_tree(paths)
        axt = expand_blocks(axt)
        axt = normalize_tree(axt)

        pp = pprint.PrettyPrinter(indent=4, stream=out)
        pp.pprint(axt)
        sys.stdout.write("-----\n")

if __name__ == '__main__':
    main(sys.argv)
