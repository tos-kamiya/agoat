#coding: utf-8

import bisect
import os
import re
import sys

from _utilities import readline_iter

import jimp_parser as jp


def indent_width(L):
    for i, c in enumerate(L):
        if c != ' ':
            return i
    return 0


def asm_file_iter(asmdir):
    for root, dirs, files in os.walk(asmdir, topdown=True):
        dirs.sort()
        files.sort()
        for f in files:
            if f.endswith(".javap"):
                yield os.path.join(root, f)


def asm_filetext_iter(asmdir):
    for asmfile in asm_file_iter(asmdir):
        yield asmfile, list(readline_iter(asmfile))


def remove_generics_args(s):
    if re.match(r"^\s+((public|private|static|final)\s+)*(java.lang.String|char) .*$", s) and \
            s.find(" = ") >= 0:
        return s

    c = ''
    p = s.find('//')
    if p >= 0:
        s, c = s[:p], s[p:]

    p = s.rfind('<')
    while p >= 0:
        q = s.find('>', p)
        assert q >= 0
        if re.match(r'^\s*$', s[:p]) and len(s) >= q + 3 and s[q+1] == ' ' and re.match(r'\w', s[q+2]):
            s = s[:p] + s[q+2:]  # such as "    <T extends Hoge> T fuga(T a);"
        else:
            s = s[:p] + s[q+1:]
        p = s.rfind('<')

    return s + c


COMPILED_FROM = 'COMPILED_FROM'
METHOD_CODE = 'METHOD_CODE'
INHERITANCE = 'INHERITANCE'


def split_into_method_iter(asmfile, lines):
    method_attribute = frozenset("public|private|protected|final|abstract|synchronized|static".split('|'))
    pat_compiled_from = re.compile(r'^Compiled from\s+"(?P<file>[^"]+)"')
    typ = r'(\w|[.$\[\]])+'
    pat_class = re.compile(r'^((public|private|final|abstract|strictfp) +)*class +(?P<id>TYP) +({|extends|implements)'.replace('TYP', typ))
    pat_interface = re.compile(r'^((public|private|abstract|strictfp) +)*interface +(?P<id>TYP) +({|extends)'.replace('TYP', typ))
    pat_static = re.compile(r'^  static +{};$')
    pat_method = re.compile(r'^  ((public|private|protected|final|abstract|synchronized|static) +)*(?P<retv>TYP) +(?P<name>[\w$]+)[(](?P<args>((TYP, )*TYP)?)[)](;| +throws)'.replace('TYP', typ))
    pat_ctor = re.compile(r'^  ((public|private|protected) +)*(?P<name>TYP)[(](?P<args>((TYP, )*TYP)?)[)](;| +throws)'.replace('TYP', typ))

    def pack(class_name, method_sig, method_body):
        if class_name == None:
            assert False
        p = class_name.find('<')
        if p >= 0:
            class_name = class_name[:p]
        return ((class_name, method_sig), method_body)

    class_name, method_sig, method_body = None, None, None

    def scan_extends_and_implements(L):
        fields = re.split('{| extends | implements ', L)
        fields = filter(None, [f.strip() for f in fields])
        lf = len(fields)
        if lf == 1:
            return (), ()
        elif lf == 2:
            return (fields[1].strip(), ), ()
        elif lf == 3:
            return (fields[1].strip(), ), tuple(filter(None, [i.strip() for i in fields[2].split(',')]))
        else:
            assert False

    for ln, L in enumerate(lines):
        if not L: continue # skip empty lines
        L = remove_generics_args(L)

        iw = indent_width(L)
        if iw == 0:
            m = pat_compiled_from.match(L)
            if m:
                yield COMPILED_FROM, m.group('file')
            else:
                m = pat_class.match(L)
                if m:
                    if class_name and method_sig:
                        yield METHOD_CODE, pack(class_name, method_sig, method_body)
                        method_sig, method_body = None, None
                    class_name = m.group('id')
                    imps, exts = scan_extends_and_implements(L)
                    yield INHERITANCE, (class_name, imps, exts)
                else:
                    m = pat_interface.match(L)
                    if m:
                        if class_name and method_sig:
                            yield METHOD_CODE, pack(class_name, method_sig, method_body)
                            method_sig, method_body = None, None
                        class_name = None
                    else:
                        if L.startswith("Compiled from ") or L == "}":
                            pass
                        else:
                            raise AssertionError("unexpected line: %s: %d: %s" % (asmfile, ln + 1, L))
        elif iw == 2:
            m = pat_method.match(L)
            if m and m.group('retv') not in method_attribute:
                if class_name and method_sig:
                    yield METHOD_CODE, pack(class_name, method_sig, method_body)
                    method_sig, method_body = None, None
                args = m.group('args') or ''
                method_sig = '\t'.join([m.group('retv'), m.group('name')] + filter(None, args.split(', ')))
                method_body = []
            else:
                m = pat_ctor.match(L)
                if m:
                    if class_name and method_sig:
                        yield METHOD_CODE, pack(class_name, method_sig, method_body)
                        method_sig, method_body = None, None
                    args = m.group('args') or ''
                    method_sig = '\t'.join(['void', '<init>'] + filter(None, args.split(', ')))
                    method_body = []
                else:
                    m = pat_static.match(L)
                    if m:
                        if class_name and method_sig:
                            yield METHOD_CODE, pack(class_name, method_sig, method_body)
                            method_sig, method_body = None, None
                        method_sig = '\t'.join(['void', '<clinit>'])
                        method_body = []
        else:
            if method_body is not None:
                method_body.append(L)

    if class_name and method_sig:
        yield METHOD_CODE, pack(class_name, method_sig, method_body)
        method_sig, method_body = None, None


def split_method_body_to_code_and_tables(method_body_lines):
    code_lines = []
    exceptiontable_lines = []
    linenumbertable_lines = []
    target = dummy = []
    for L in method_body_lines:
        if L == "    Code:":
            target = code_lines
        elif L == "    Exception table:":
            target = exceptiontable_lines
        elif L == "    LineNumberTable:":
            target = linenumbertable_lines
        elif L == "    LocalVariableTable:":
            target = dummy
        else:
            target.append(L)
    return code_lines, exceptiontable_lines, linenumbertable_lines


ASM_FILE = 'ASM_FILE'


def get_asm_info_iter(asm_dir):
    """
    Iterate each method definition of each disassembled file in 'asm_dir' directory.
    Yielded values
       typ: ASM_FILE, COMPILED_FROM, METHOD_CODE, or INHERITANCE
       values: string or tuple
       
       when typ == ASM_FILE, values is a string, name of a disassembled file.

       when COMPILED_FROM == 'COMPILED_FROM', values is a string,
         name of source file recorded in bytecode.

       when typ == METHOD_CODE, values is a tuple, which contains:
         sig: signature of the method (str)
         code: definition of the method (list of str)
         exception table: exception table of the method (list of str)
         linenum_table: line number table (list of str)

       when typ == INHERITANCE, values is a tuple, which contains:
         claz: (str)
         extends: its exntending classes (list of str, length is 0 or 1)
         implements: its implementing interfaces (list of str)
    """

    def search_asmdir(asmdir):
        for asmfile, lines in asm_filetext_iter(asmdir):
            yield ASM_FILE, asmfile
            for v in split_into_method_iter(asmfile, lines):
                yield v

    for typ, values in search_asmdir(asm_dir):
        if typ in (ASM_FILE, COMPILED_FROM, INHERITANCE):
            yield typ, values
        elif typ == METHOD_CODE:
            claz_sig, body = values
            code, exception_table, linenum_table = split_method_body_to_code_and_tables(body)
            yield typ, (claz_sig, code, exception_table, linenum_table)
        else:
            assert False


def scan_linumber_table(text):
    lineseq, indexseq = [], []
    pat = re.compile(r'^\s+line\s+(\d+):\s+(\d+)$')
    for L in text:
        m = pat.match(L)
        assert m
        lineseq.append(int(m.group(1)))
        indexseq.append(int(m.group(2)))
    return lineseq, indexseq


def sig_to_source_file(sig):
    p = sig.index('.')
    q = sig.find('$')
    if q >= 0 and q < p:
        p = q
    possible_source_file = sig[:p] + '.java'
    reference = sig[p+1:]
    return possible_source_file, reference


def convert_location_from_index_to_linenum(L, sig2filename_linenumber_table):
    is_call_thru = False
    if L.startswith("* "):
        L = L[2:]
        is_call_thru = True
    p = L.rindex(' >')
    depth = int(L[p+2:])
    L = L[:p]
    p = L.rindex(',')
    sig, index = L[:p], int(L[p+1:])
    source_file, ls_is = sig2filename_linenumber_table.get(sig)
    assert ls_is != None
    lineseq, indexseq = ls_is
    i = bisect.bisect_right(indexseq, index) - 1
    assert i >= 0
    linenum = lineseq[i]
    _, reference = sig_to_source_file(sig)
    return (source_file, linenum, depth, reference, is_call_thru)

# def to_pseudo_source_file_name(claz):
#     p = claz.find('$')
#     if p >= 0:
#         claz = claz[:p]
#     return claz + ".java"


def make_invocationindex_to_src_linenum_table(javap_asm_dir):
    pat_invokes = re.compile(r"^\s+(\d+):\s+invoke.*$")
    claz_msig2invocationindex2linenum = {}  # (str, msig) -> [int]
    for typ, values in get_asm_info_iter(javap_asm_dir):
        if typ == METHOD_CODE:
            claz_sig, code, etbl, ltbl = values
            clzmsig = '%s\t%s' % claz_sig
            invocationindex2linenum = []
            lineseq, indexseq = scan_linumber_table(ltbl)
            for L in code:
                m = pat_invokes.match(L)
                if m:
                    index = int(m.group(1))
                    i = bisect.bisect_right(indexseq, index) - 1
                    assert i >= 0
                    linenum = lineseq[i]
                    invocationindex2linenum.append(linenum)
            claz_msig2invocationindex2linenum[clzmsig] = invocationindex2linenum
    return claz_msig2invocationindex2linenum


def jimp_linnum_to_src_linenum_table(class_table, claz_msig2invocationindex2linenum):
    clz_msig2conversion = {}  # clz_msig -> jimp_linenum -> src_linenum
    for clz, cd in sorted(class_table.iteritems()):
        for clzmsig, md in sorted(cd.methods.iteritems()):
            invocationindex2linenum = claz_msig2invocationindex2linenum.get(clzmsig)
            if invocationindex2linenum:
                conversion = {}
                clz_msig2conversion[clzmsig] = conversion
                invocationindex = -1
                for ins in md.code:
                    if ins and ins[0] in (jp.INVOKE, jp.SPECIALINVOKE):
                        invocationindex += 1
                        assert isinstance(ins[-1], int)
                        jimp_linenum = ins[-1]
                        conversion[jimp_linenum] = invocationindex2linenum[invocationindex]
    return clz_msig2conversion


if __name__ == '__main__':
    t = make_invocationindex_to_src_linenum_table(sys.argv[1])
#    print repr(t)

