#coding: utf-8

import os
import sys

from . import _run_javap
from . import _run_soot


def class_filename_to_class_name(L):
    L = L[:L.rfind('.')]
    if L.startswith("./"):
        L = L[2:]
    L = L.replace("/", ".")
    return L


def find_classes(target_dir):
    clzs = []
    cur_dir = os.path.abspath(os.curdir)
    try:
        os.chdir(target_dir)
        for root, dirs, files in os.walk(os.curdir):
            for f in files:
                if f.endswith(".class"):
                    clz = class_filename_to_class_name(os.path.join(root, f))
                    clzs.append(clz)
    finally:
        os.chdir(cur_dir)
    clzs.sort()

    return clzs


def main(argv):
    args = argv[1:]
    if not args or args[0] in ('-h', '--help'):
        sys.stdout.write("usage: run_disasms target_dir\n")
        return
    if len(args) > 1:
        sys.exit("too many command-line arguments")
    target_dir = args[0]

    clzs = find_classes(target_dir)
    _run_javap.disassemble(_run_javap.output_dir, target_dir, clzs)
    _run_soot.disassemble(_run_soot.output_dir, target_dir, clzs)


if __name__ == '__main__':
    main(sys.argv)