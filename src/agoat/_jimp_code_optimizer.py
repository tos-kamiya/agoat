# coding: utf-8

from . import jimp_parser as jp


def merge_labels(inss):
    label_order = {}
    for i, ins in enumerate(inss):
        cmd = ins[0]
        if cmd == jp.LABEL:
            label_order[ins[1]] = i

    reduced = []
    label_replace = {}
    for i, ins in enumerate(inss):
        cmd = ins[0]
        if cmd == jp.LABEL and \
                reduced and reduced[-1][0] == jp.LABEL:
            src = reduced[-1][1]
            dst = ins[1]
            assert label_order[src] < label_order[dst]
            label_replace[src] = dst
            reduced.pop()
            reduced.append(ins)
        elif cmd == jp.GOTO and \
                reduced and reduced[-1][0] == jp.LABEL:
            src = reduced[-1][1]
            dst = ins[1]
            if label_order[src] < label_order[dst]:
                label_replace[src] = dst
                reduced.pop()
                reduced.append(ins)
            else:
                reduced.append(ins)
        else:
            reduced.append(ins)

    src_dsts = list(label_replace.iteritems())
    for src, dst in src_dsts:
        srcs = [src]
        d = dst
        while d in label_replace:
            nd = label_replace[d]
            if nd in srcs:
                break  # while dst
            srcs.append(d)
            d = nd
        if d != dst:
            label_replace[src] = d

    if label_replace:
        for i, ins in enumerate(reduced):
            cmd = ins[0]
            if cmd in (jp.IFGOTO, jp.GOTO):
                r = label_replace.get(ins[1])
                if r:
                    rins = [cmd, r]
                    rins.extend(ins[2:])
                    reduced[i] = tuple(rins)
            elif cmd == jp.SWITCH:
                dests = ins[1]
                rds = []
                for d in dests:
                    r = label_replace.get(d)
                    rds.append(r if r else d)
                rins = [jp.SWITCH, rds]
                rins.extend(ins[2:])
                reduced[i] = tuple(rins)
    return reduced


def remove_redundant_gotos(inss):
    reduced = []
    for i, ins in enumerate(inss):
        cmd = ins[0]
        if cmd in jp.IFGOTO:
            found = False
            for prev in reversed(reduced):
                if prev[0] != jp.IFGOTO:
                    break  # for prev
                if prev[1] == ins[1]:
                    found = True
                    break  # for prev
            if found:
                pass
            else:
                reduced.append(ins)
        elif cmd in jp.GOTO:
            if reduced and reduced[-1] == jp.GOTO:
                pass
            else:
                reduced.append(ins)
        elif cmd == jp.LABEL:
            if reduced and reduced[-1][0] in (jp.IFGOTO, jp.GOTO) and reduced[-1][1] == ins[1]:
                reduced.pop()
            reduced.append(ins)
        elif cmd == jp.SWITCH:
            dests = ins[1]
            dest_set = set()
            rds = []
            for d in dests:
                if d not in dest_set:
                    rds.append(d)
                    dest_set.add(d)
            rins = [jp.SWITCH, rds]
            rins.extend(ins[2:])
            reduced.append(tuple(rins))
        else:
            reduced.append(ins)
    return reduced


def optimize_ins_seq(inss):
    inss = merge_labels(inss)
    inss = remove_redundant_gotos(inss)
    return inss
