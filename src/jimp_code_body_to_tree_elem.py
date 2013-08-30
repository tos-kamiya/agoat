#coding: utf-8

try:
    from sys import intern  # py3k
except:
    pass

import sys
from collections import Counter, defaultdict
import pprint

from _utilities import sort_uniq

import jimp_parser as jp
import jimp_code_optimizer as jco
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

BOX = 'box'

def make_boxes(inss):
    label2dest = {}
    for i, ins in enumerate(inss):
        if ins[0] == jp.LABEL:
            label2dest[ins[1]] = i

    escape_edges = defaultdict(list)
    for i, ins in enumerate(inss):
        if ins[0] in (jp.GOTO, jp.IFGOTO):
            src, dest = i, label2dest[ins[1]]
            escape_edges[dest].append(src)
            escape_edges[src].append(dest)
        elif ins[0] == jp.SWITCH:
            src = i
            for d in ins[1]:
                dest = label2dest[d]
                escape_edges[dest].append(src)
                escape_edges[src].append(dest)
    for v in escape_edges.itervalues():
        v[:] = sort_uniq(v)
    
    boxed_inss = []
    len_inss = len(inss)
    i = 0
    while i < len_inss:
        escaping_prev = False
        nexti = None
        for j in range(i + 1, len_inss):
            # [i..j) is  a candidate of box
            escaping_post = False
            for index in range(i, j):
                escapes = escape_edges[index]
                for e in escapes:
                    if e < i:
                        escaping_prev = True
                        break  # for e
                    elif e >= j:
                        escaping_post = True
                        break  # for e
                if escaping_prev or escaping_post:
                    break  # for index
            if escaping_prev:
                break  # for j
            elif not escaping_post and (i, j) != (0, len_inss):
                inner_boxes = inss[i:j]
                inner_boxes = make_boxes(inner_boxes)
                if len(inner_boxes) == 1:
                    boxed_inss.append(inner_boxes[0])
                else:
                    box = [BOX]
                    box.extend(inner_boxes)
                    boxed_inss.append(box)
                nexti = j
                break  # for j
        if nexti is None:  # not found any box
            boxed_inss.append(inss[i])
            nexti = i + 1
        i = nexti
    return boxed_inss

BLOCK = 'block'

def make_basic_blocks(inss):
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
        elif cmd == BOX:
            b = [BOX]
            b.extend(make_basic_blocks(ins[1:]))
            bis.append(b)
        else:
            assert False
    if cur_block is not None:
        bis.append(cur_block)
    return bis

def make_nested_blocks(bis):
    label2targetcount = Counter()
    for i, ins in enumerate(bis):
        if ins[0] in (jp.GOTO, jp.IFGOTO):
            label2targetcount[ins[1]] += 1
        elif ins[0] == jp.SWITCH:
            for dest in ins[1]:
                label2targetcount[dest] += 1

    def is_loop_pattern(lbl0, ifgoto1, goto2, lbl3):
        if not (lbl0[0] == jp.LABEL and ifgoto1[0] == jp.IFGOTO and goto2[0] == jp.GOTO and lbl3[0] == jp.LABEL):
            return False
        lbl0, ifgoto1, goto2, lbl3 = lbl0[1], ifgoto1[1], goto2[1], lbl3[1]
        if lbl0 == goto2 and label2targetcount.get(lbl0) == 1 and lbl3 == ifgoto1 and label2targetcount.get(lbl3) == 1:
            return True
    
    def recurse_if_box(item):
        if item and item[0] == BOX:
            b = [BOX]
            b.extend(make_nested_blocks(item[1:]))
            return b
        else:
            return item

    while True:
        new_box_found = False
        label2dest = {}
        for i, ins in enumerate(bis):
            if ins[0] == jp.LABEL:
                label2dest[ins[1]] = i

        nb = []
        len_bis = len(bis)
        i = 0
        while i < len_bis:
            eat = False
            
            # loop patterns
            if not eat and i + 5 < len_bis:
                ss = bis[i:i + 5]
                if is_loop_pattern(ss[0], ss[1], ss[2], ss[3]):
                    i += 4
                    eat = True
                    new_box_found = True
            if not eat and i + 5 < len_bis:
                ss = bis[i:i + 5]
                if ss[2][0] in (BLOCK, BOX) and is_loop_pattern(ss[0], ss[1], ss[3], ss[4]):
                    nb.append(recurse_if_box(ss[2]))
                    i += 5
                    eat = True
                    new_box_found = True
            if not eat and i + 5 < len_bis:
                ss = bis[i:i + 5]
                if ss[1][0] in (BLOCK, BOX) and is_loop_pattern(ss[0], ss[2], ss[3], ss[4]):
                    nb.append(recurse_if_box(ss[1]))
                    i += 5
                    eat = True
                    new_box_found = True
            if not eat and i + 6 < len_bis:
                ss = bis[i:i + 6]
                if ss[1][0] in (BLOCK, BOX) and ss[3][0] in (BLOCK, BOX) and is_loop_pattern(ss[0], ss[2], ss[4], ss[5]):
                    if ss[1][0] == BLOCK and ss[3][0] == BLOCK:
                        merged_block = [BLOCK]
                        merged_block.extend(ss[1])
                        merged_block.extend(ss[3])
                        nb.append(merged_block)
                    else:
                        b = [BOX]
                        b.appnd(recurse_if_box(ss[1]))
                        b.appnd(recurse_if_box(ss[3]))
                        nb.append(b)
                    i += 6
                    eat = True
                    new_box_found = True
#             
#             # swtich-case patterns
#             if not eat and bis[i][0] == jp.SWITCH:
#                 merged_block = [ORDERED_XOR]
#                 matching_pattern = True
#                 exit_label = None
#                 destlabel2count = Counter()
#                 for dest in bis[i][1]:
#                     if exit_label is not None and dest == exit_label:  # in case of default: case
#                         merged_block.append([ORDERED_AND])
#                         destlabel2count[exit_label] += 1
#                         continue
#                     dest_index = label2dest.get(dest)
#                     if dest_index is None:
#                         assert False
#                     destlabel2count[dest] += 1
#                     if dest_index + 2 < len_bis and \
#                             bis[dest_index + 1][0] in (jp.GOTO, jp.LABEL) and (exit_label is None or bis[dest_index + 1][1] == exit_label):
#                         exit_label = bis[dest_index + 1][1]
#                         if bis[dest_index + 1][0] == jp.GOTO:
#                             destlabel2count[exit_label] += 1
#                     elif dest_index + 3 < len_bis and \
#                             bis[dest_index + 1][0] == BLOCK and \
#                             bis[dest_index + 2][0] in (jp.GOTO, jp.LABEL) and (exit_label is None or bis[dest_index + 2][1] == exit_label):
#                         exit_label = bis[dest_index + 2][1]
#                         if bis[dest_index + 2][0] == jp.GOTO:
#                             destlabel2count[exit_label] += 1
#                         merged_block.append(bis[dest_index + 1])
#                     else:
#                         matching_pattern = False
#                         break  # for dest
#                 if matching_pattern and exit_label is not None:
#                     jump_from_outer = False
#                     for l, c in destlabel2count.iteritems():
#                         if label2targetcount.get(l) != c:
#                             jump_from_outer = True
#                             break  # for l, c
#                     nexti = label2dest.get(exit_label) + 1
#                     unconsumed_label_inside = any((ins[0] == jp.LABEL and ins[0] not in destlabel2count) \
#                             for ins in bis[i:nexti])
#                     if not jump_from_outer and not unconsumed_label_inside:
#                         if len(merged_block) == 2:
#                             merged_block = merged_block[1]
#                         nb.append([BLOCK, merged_block])
#                         assert nexti > i
#                         i = nexti
#                         eat = True
#                         new_box_found = True
#             
#             # if patterns
#             if not eat and i + 3 < len_bis and \
#                     [ins[0] for ins in bis[i:i + 3]] == [jp.IFGOTO, BLOCK, jp.LABEL] and \
#                     bis[i][1] == bis[i + 2][1] and label2targetcount.get(bis[i + 2][1]) == 1:
#                 nb.append([BLOCK, [ORDERED_XOR, bis[i + 1], [ORDERED_AND]]])
#                 i += 3
#                 eat = True
#                 new_box_found = True
#             if not eat and i + 5 < len_bis and \
#                     [ins[0] for ins in bis[i:i + 5]] == [jp.IFGOTO, jp.GOTO, jp.LABEL, BLOCK, jp.LABEL] and \
#                     bis[i][1] == bis[i + 2][1] and label2targetcount.get(bis[i + 2][1]) == 1 and \
#                     bis[i + 1][1] == bis[i + 4][1] and label2targetcount.get(bis[i + 4][1]) == 1: 
#                 nb.append([BLOCK, [ORDERED_XOR, bis[i + 3], [ORDERED_AND]]])
#                 i += 5
#                 eat = True
#                 new_box_found = True
#             if not eat and i + 6 < len_bis and \
#                     [ins[0] for ins in bis[i:i + 6]] == [jp.IFGOTO, BLOCK, jp.GOTO, jp.LABEL, BLOCK, jp.LABEL] and \
#                     bis[i][1] == bis[i + 3][1] and label2targetcount.get(bis[i + 3][1]) == 1 and \
#                     bis[i + 2][1] == bis[i + 5][1] and label2targetcount.get(bis[i + 5][1]) == 1: 
#                 nb.append([BLOCK, [ORDERED_XOR, bis[i + 1], bis[i + 4]]])
#                 i += 6
#                 eat = True
#                 new_box_found = True
            
            if not eat:
                nb.append(bis[i])
                i += 1
        if not new_box_found:
            break  # while True
        bis = nb
    return bis

def count_branches(inss):
    c = 0
    for i, ins in enumerate(inss):
        cmd = ins[0]
        if cmd in (jp.RETURN, jp.THROW, jp.IFGOTO):
            c += 1
        elif cmd == jp.SWITCH:
            c += len(ins[1])
    return c

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

def copy_counter(c):
    d = Counter()
    for k, v in c.iteritems():
        d[k] = v
    return d

def convert_to_execution_paths(inss):
    if inss and inss[0] == BLOCK:
        return inss

    len_inss = len(inss)
    label2dest = {}
    for i, ins in enumerate(inss):
        if ins[0] == jp.LABEL:
            label2dest[ins[1]] = i
 
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
                    branched_path = nesting_dup(path)
                    path = nesting_dup(path)
                    branched_visitedlabels = copy_counter(visitedlabels)
                    branches.append((label2dest[dest], branched_path, branched_visitedlabels))
            elif cmd == jp.GOTO:
                dest = ins[1]
                dest_index = label2dest.get(dest)
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
                        branched_path = nesting_dup(path)
                        branched_visitedlabels = copy_counter(visitedlabels)
                        branches.append((label2dest[dest], branched_path, branched_visitedlabels))
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
    if not paths:
        return [ORDERED_AND]
    t = [ORDERED_XOR]
    for p in paths:
        pt = [ORDERED_AND]
        for i in p:
            if i and i[0] == BOX:
                pt.append(paths_to_ordred_andxor_tree(i[1:]))
            else:
                assert isinstance(i, tuple) or i and i[0] == BLOCK
                pt.append(i)
        t.append(pt)
    return normalize_tree(t)

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
            bis = make_basic_blocks(inss)
            bis = make_boxes(bis)
            nbis = make_nested_blocks(bis)
            obis = jco.optimize_ins_seq(nbis)
            nbranch = count_branches(obis)
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
        bis = make_basic_blocks(inss)
        bis = make_boxes(bis)
        nbis = make_nested_blocks(bis)
        obis = jco.optimize_ins_seq(nbis)
        nbranch = count_branches(obis)
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
