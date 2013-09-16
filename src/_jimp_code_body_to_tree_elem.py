# coding: utf-8

try:
    from sys import intern  # py3k
except:
    pass

import sys
import pprint
from collections import Counter
import itertools

from _utilities import sort_uniq
import jimp_parser as jp
import _jimp_code_optimizer as jco
from andor_tree import ORDERED_AND, ORDERED_OR, normalize_tree
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


def gen_type_resolver(method_data, class_data):
    def resolve_type(name):
        if name == 'null':
            return 'null', None
        if name is None:
            return None, None
        if name.startswith("class "):
            return 'java.lang.Class', None
        elif name in ("true", "false"):
            return 'boolean', None
        elif name.startswith("'"):
            return "char", None
        elif name.startswith('"'):
            return "java.lang.String", name
        elif name[0] in "-+0123456789":
            s = name[-1]
            if s == 'L':
                return 'long', None
            elif s == 'F':
                return 'float', None
            elif s == 'D':
                return 'double', None
            else:
                return 'int', None
        t = method_data.fields.get(name)
        if t:
            return intern(t), None
        t = class_data.fields.get(name)
        if t:
            return intern(t), None
        return None, None
    return resolve_type


def resolve_types_in_code(inss, method_data, class_data):
    assert inss is not None

    resolve_type = gen_type_resolver(method_data, class_data)
    resolved_inss = []
    for ins in inss:
        cmd = ins[0]
        if cmd in (jp.SPECIALINVOKE, jp.INVOKE):
            literals = set()
            receiver, method_name, args, retv, linenum = ins[1:]
            rrecv, lit = resolve_type(receiver)
            if rrecv is None:
                rrecv = receiver
            lit and literals.add(lit)
            rargs = []
            for a in args:
                rarg, lit = resolve_type(a)
                lit and literals.add(lit)
                rargs.append(rarg)
            rargs = tuple(rargs)
            rretv, lit = resolve_type(retv)
            lit and literals.add(lit)
            msig = method_sig_intern(jp.MethodSig(rretv, method_name, rargs))
            literals = tuple(sorted(literals))
            resolved_inss.append((cmd, rrecv, msig, literals, linenum))
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
                # cmd, receiver, method_name, args, retv, lterals, linenum = ins
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
                    branches.append(
                        (label2index[dest], nesting_dup(path), visitedlabels.copy()))
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
                        branches.append(
                            (label2index[dest], nesting_dup(path), visitedlabels.copy()))
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


def paths_to_ordred_andor_tree(paths):
    if not paths:
        return [ORDERED_AND]

    def keyfunc(path):
        len_path = len(path)
        if len_path >= 2:
            return id(path[0]), id(path[-1])
        elif len_path == 1:
            return id(path), None
        else:
            return None, None

    def have_same_id(items):
        assert items
        id0 = id(items[0])
        return all(id(item) == id0 for item in items[1:])

    def split_prefix(paths):
        if len(paths) == 1:
            return paths[0], [[]]
        prefix = []
        for items in zip(*paths):
            if have_same_id(items):
                prefix.append(items[0])
            else:
                break  # for items
        len_prefix = len(prefix)
        paths = [p[len_prefix:] for p in paths]
        return prefix, paths

    if len(paths) == 1:
        converted = [ORDERED_AND] + paths[0]
    else:
        converted = [ORDERED_OR]
        for k, g in itertools.groupby(sorted(paths, key=keyfunc), key=keyfunc):
            pths = list(g)
            if len(pths) == 1:
                converted.append([ORDERED_AND] + pths[0])
            else:
                prefix = []
                if k[0] is not None:
                    prefix, pths = split_prefix(pths)
                postfix = []
                if all(len(p) > 0 for p in pths):
                    if k[1] is not None:
                        pths = [list(reversed(p)) for p in pths]
                        postfix, pths = split_prefix(pths)
                        postfix = list(reversed(postfix))
                        pths = [list(reversed(p)) for p in pths]
                t = [ORDERED_AND]
                t.extend(prefix)
                t.append([ORDERED_OR] + [[ORDERED_AND] + p for p in pths])
                t.extend(postfix)
                converted.append(t)

    def convert_internal_box(node):
        if isinstance(node, list):
            assert node
            n0 = node[0]
            if n0 == BOX:
                return paths_to_ordred_andor_tree(node[1:])
            if n0 in (ORDERED_AND, ORDERED_OR):
                t = [n0]
                t.extend(convert_internal_box(n) for n in node[1:])
                return t
            else:
                assert n0 == BLOCK
                return node
        else:
            return node

    internal_box_converted = convert_internal_box(converted)
    return normalize_tree(internal_box_converted)


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
        elif n0 in (ORDERED_AND, ORDERED_OR):
            subns = [expand_blocks(subn) for subn in node[1:]]
            return [n0] + subns
        else:
            assert False
    else:
        return node


class BranchCountExceedingLimitation(ValueError):
    pass


def inss_to_tree(method_data, class_data, branches_atmost=None):
    inss = resolve_types_in_code(method_data.code, method_data, class_data)
    bis = _jimp_code_box_generator.make_block_and_box(inss)
    obis = jco.optimize_ins_seq(bis)
    nbranch = get_max_branches_of_boxes(obis)
    if branches_atmost is not None and nbranch > branches_atmost:
        raise BranchCountExceedingLimitation()
    else:
        paths = convert_to_execution_paths(obis)
        aot = paths_to_ordred_andor_tree(paths)
        aot = expand_blocks(aot)
        aot = normalize_tree(aot)
        return aot


def inss_to_tree_in_class_table(class_table, branches_atmost=None, progress_repo=None):
    new_tbl = {}  # str -> ClassData
    for clz, cd in class_table.iteritems():
        new_tbl[clz] = new_cd = jp.ClassData(cd.class_name, cd.base_name, interf_names=cd.interf_names)
        for msig, md in cd.methods.iteritems():
            progress_repo and progress_repo(current=(cd.class_name, md.method_sig))

            new_md = jp.MethodData(md.method_sig, md.scope_class)
            new_md.fields = md.fields
            new_md.code = inss_to_tree(md, cd, branches_atmost=branches_atmost)
            new_cd.methods[msig] = new_md
    return new_tbl


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
        inss = resolve_types_in_code(md.code, md, cd)
#         out.write("%s, %s:\n" % (clz, method_sig))
#         for ins in inss:
#             out.write("  %s\n" % repr(ins))
        bis = _jimp_code_box_generator.make_block_and_box(inss)
        obis = jco.optimize_ins_seq(bis)
        nbranch = get_max_branches_of_boxes(obis)
        out.write("branches: %d\n" % nbranch)
        paths = convert_to_execution_paths(obis)
        aot = paths_to_ordred_andor_tree(paths)
        aot = expand_blocks(aot)
        aot = normalize_tree(aot)

        pp = pprint.PrettyPrinter(indent=4, stream=out)
        pp.pprint(aot)
        sys.stdout.write("-----\n")

if __name__ == '__main__':
    main(sys.argv)
