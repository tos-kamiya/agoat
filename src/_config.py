#coding: utf-8

import sys

VERSION = "0.5.0"

default_calltree_path = 'agoat.calltree'
default_linenumbertable_path = 'agoat.linenumbertable'
default_javap_dir_path = 'javapOutput'
default_soot_dir_path = 'sootOutput'
defalut_max_depth_of_subtree = 5

if sys.platform == "win32":
    import os
    import msvcrt
    msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)
    msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
