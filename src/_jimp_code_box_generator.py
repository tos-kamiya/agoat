# coding: utf-8

from collections import defaultdict, Counter

from _utilities import sort_uniq

import jimp_parser as jp

# BLOCK is a sequence of instructions, which does not any kind of branches
# (goto, etc)
BLOCK = 'block'

# BOX is a sequence possibly including branches but without any incoming
# or outgoing branches to out of the box
BOX = 'box'


def get_label2index(inss):
    label2index = {}
    for i, ins in enumerate(inss):
        if ins[0] == jp.LABEL:
            label2index[ins[1]] = i
    return label2index


def make_boxes(inss):
    label2index = get_label2index(inss)

    escape_edges = defaultdict(list)
    for i, ins in enumerate(inss):
        if ins[0] in (jp.GOTO, jp.IFGOTO):
            src, dest = i, label2index[ins[1]]
            escape_edges[dest].append(src)
            escape_edges[src].append(dest)
        elif ins[0] == jp.SWITCH:
            src = i
            for d in ins[1]:
                dest = label2index[d]
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
        label2index = get_label2index(bis)

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
# swtich-case patterns
#             if not eat and bis[i][0] == jp.SWITCH:
#                 merged_block = [ORDERED_OR]
#                 matching_pattern = True
#                 exit_label = None
#                 destlabel2count = Counter()
#                 for dest in bis[i][1]:
# if exit_label is not None and dest == exit_label:  # in case of default: case
#                         merged_block.append([ORDERED_AND])
#                         destlabel2count[exit_label] += 1
#                         continue
#                     dest_index = label2index.get(dest)
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
# break  # for dest
#                 if matching_pattern and exit_label is not None:
#                     jump_from_outer = False
#                     for l, c in destlabel2count.iteritems():
#                         if label2targetcount.get(l) != c:
#                             jump_from_outer = True
# break  # for l, c
#                     nexti = label2index.get(exit_label) + 1
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
# if patterns
#             if not eat and i + 3 < len_bis and \
#                     [ins[0] for ins in bis[i:i + 3]] == [jp.IFGOTO, BLOCK, jp.LABEL] and \
#                     bis[i][1] == bis[i + 2][1] and label2targetcount.get(bis[i + 2][1]) == 1:
#                 nb.append([BLOCK, [ORDERED_OR, bis[i + 1], [ORDERED_AND]]])
#                 i += 3
#                 eat = True
#                 new_box_found = True
#             if not eat and i + 5 < len_bis and \
#                     [ins[0] for ins in bis[i:i + 5]] == [jp.IFGOTO, jp.GOTO, jp.LABEL, BLOCK, jp.LABEL] and \
#                     bis[i][1] == bis[i + 2][1] and label2targetcount.get(bis[i + 2][1]) == 1 and \
#                     bis[i + 1][1] == bis[i + 4][1] and label2targetcount.get(bis[i + 4][1]) == 1:
#                 nb.append([BLOCK, [ORDERED_OR, bis[i + 3], [ORDERED_AND]]])
#                 i += 5
#                 eat = True
#                 new_box_found = True
#             if not eat and i + 6 < len_bis and \
#                     [ins[0] for ins in bis[i:i + 6]] == [jp.IFGOTO, BLOCK, jp.GOTO, jp.LABEL, BLOCK, jp.LABEL] and \
#                     bis[i][1] == bis[i + 3][1] and label2targetcount.get(bis[i + 3][1]) == 1 and \
#                     bis[i + 2][1] == bis[i + 5][1] and label2targetcount.get(bis[i + 5][1]) == 1:
#                 nb.append([BLOCK, [ORDERED_OR, bis[i + 1], bis[i + 4]]])
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


def make_block_and_box(inss):
    bis = make_basic_blocks(inss)
    bis = make_boxes(bis)
    bis = make_nested_blocks(bis)
    return bis
