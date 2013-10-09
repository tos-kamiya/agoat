#!/usr/bin/env python2

import sys

import agoat._config
import agoat.run_disasms
import agoat.indexer
import agoat.diagnostic
import agoat.querysearcher

USAGE = "usage: %s {disasm,index,list,query} [-h|--version]\n"


def main(argv):
    if len(argv) == 1 or argv[1] in ("-h", "--help"):
        sys.stdout.write(USAGE % argv[0])
        return
    elif argv[1] == "--version":
        sys.stdout.write("%s version %s\n" % (argv[0], agoat._config.VERSION))
        return

    cmd = argv[1]
    argv = argv[:]
    del argv[1]
    argv[0] = argv[0] + " " + cmd

    if cmd == 'disasm':
        agoat.run_disasms.main(argv)
    elif cmd == 'index':
        agoat.indexer.main(argv)
    elif cmd == 'list':
        agoat.diagnostic.main(argv)
    elif cmd == 'query':
        agoat.querysearcher.main(argv)
    else:
        sys.exit("unknown command: %s" % cmd)


if __name__ == '__main__':
    main(sys.argv)