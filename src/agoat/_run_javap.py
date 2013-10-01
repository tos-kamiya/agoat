#coding: utf-8

import os
import sys
import subprocess
import multiprocessing


output_dir = "javapOutput"


def javap_disassemble(a):
    output_dir, clz, class_path = a
    disassembled = subprocess.check_output(["/usr/bin/javap", "-cp", class_path, "-c", "-l", clz])
    fp = os.path.join(output_dir, clz + ".javap")
    with open(fp, "wb") as f:
        f.write(disassembled)


def disassemble(output_dir, class_path, clzs):
    if not os.path.exists(output_dir):
        os.mkdir(output_dir)

#     for clz in clzs:
#         javap_disassemble(output_dir, clz, class_path)
    pool = multiprocessing.Pool(4)
    pool.map(javap_disassemble, [(output_dir, clz, class_path) for clz in clzs])


def main(argv):
    args = argv[1:]
    if not args or args[0] in ('-h', '--help'):
        sys.stdout.write("usage: run_javap class_list_file -cp class_path\n")
        return
    if len(args) != 3:
        sys.exit("invalid command line")

    class_list_file = args[0]
    assert args[1] in ("-c", "--class-path", "-cp", "-classpath")
    class_path = args[2]

    with open(class_list_file, "rb") as f:
        clzs = f.read().split('\n')
    clzs = sorted(filter(None, clzs))

    disassemble(output_dir, class_path, clzs)


if __name__ == '__main__':
    main(sys.argv)
