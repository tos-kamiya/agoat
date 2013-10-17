#coding: utf-8

import os
import sys
import argparse

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


def build_argument_parser(psr):
    psr.add_argument("targetdir", action='store')


def main(argv):
    psr = argparse.ArgumentParser(prog=argv[0], description='agoat disassembler runner')
    build_argument_parser(psr)

    args = psr.parse_args(argv[1:])
    target_dir = args.targetdir

    clzs = find_classes(target_dir)
    _run_javap.disassemble(_run_javap.output_dir, target_dir, clzs)
    _run_soot.disassemble(_run_soot.output_dir, target_dir, clzs)


if __name__ == '__main__':
    main(sys.argv)