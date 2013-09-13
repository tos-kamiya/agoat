#coding: utf-8

import os
import sys
import subprocess
import re


output_dir = "sootOutput"
log_file = "agoat.soot_log"


def find_soot_jar():
    cur_dir = os.path.dirname(os.path.abspath(__file__))
    prev_dir = None
    while prev_dir != cur_dir:
        files = os.listdir(cur_dir)
        for f in files:
            if re.match(r"^soot-[\d.]*[.]jar$", f):
                return os.path.join(cur_dir, f)
        prev_dir = cur_dir
        cur_dir = os.path.dirname(cur_dir)
    sys.exit("no 'soot-*.jar' found. put it in the directory of 'run_soot.py'")


SOOT_JAR = find_soot_jar()


def soot_disassemble(output_dir, clz, class_path, failed_clzs=[]):
    try:
        subprocess.check_call([
            "/usr/bin/java", "-jar", SOOT_JAR, "-cp", class_path, 
            "-pp", "-f", "j", clz,
            "-d", output_dir
        ])
    except subprocess.CalledProcessError:
        failed_clzs.append(clz)


def disassemble(output_dir, class_path, clzs):
    if not os.path.exists(output_dir):
        os.mkdir(output_dir)

    failed_clzs = []
    for clz in clzs:
        soot_disassemble(output_dir, clz, class_path, failed_clzs)

    if failed_clzs:
        with open(log_file, "wb") as out:
            out.write("# disassembling fails to the following classes:\n")
            for fc in failed_clzs:
                out.write("%s\n" % fc)


def main(argv):
    args = argv[1:]
    if not args or args[0] in ('-h', '--help'):
        sys.stdout.write("usage: run_soot class_list_file -cp class_path\n")
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
