#coding: utf-8

import os
import sys
import subprocess
import multiprocessing


def javap_disassemble(a):
    javap_output_dir, clz, class_path = a
    disassembled = subprocess.check_output(["/usr/bin/javap", "-cp", class_path, "-c", "-l", clz])
    fp = os.path.join(javap_output_dir, clz + ".javap")
    with open(fp, "wb") as f:
        f.write(disassembled)


def main(argv):
    javap_output_dir = "javapOutput"

    class_list_file = argv[1]
    assert argv[2] in ("-c", "--class-path", "-cp", "-classpath")
    class_path = argv[3]

    if not os.path.exists(javap_output_dir):
        os.mkdir(javap_output_dir)

    with open(class_list_file, "rb") as f:
        clzs = f.read().split('\n')

#     for clz in clzs:
#         javap_disassemble(javap_output_dir, clz, class_path)
    pool = multiprocessing.Pool(4)
    pool.map(javap_disassemble, [(javap_output_dir, clz, class_path) for clz in clzs if clz])


if __name__ == '__main__':
    main(sys.argv)
