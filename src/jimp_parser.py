#coding: utf-8

import re
import sys
from collections import namedtuple

from _utilities import readline_iter

_IDENTIFIER = "[\w.$]+"
_TYPE = r"([\w.$]|\[|\])+"

_PAT_DECL = re.compile(r"^\s+" +
        r"((public|private|final|static|synchronized)\s+)*" +
        r"(?P<typ>%s\s+)" % _TYPE +
        r"(?P<name>%s)" % _IDENTIFIER + 
        r";" +
        r"$")

_PAT_CLASS_DEF_HEAD = re.compile(r"^" + 
        r"(public|private|final)\s*" + 
        r"class\s+(?P<class_name>%s)" % _IDENTIFIER + 
        r"(\s+extends\s+(?P<base_name>%s))" % _IDENTIFIER +
        r"(\s+implements\s+.*)?" + 
        r"$")
# _PAT_CLASS_DEF_BEGIN = re.compile("^" + "{" + "$")
_PAT_CLASS_DEF_END = re.compile("^" + "}" + "$")

_PAT_METHOD_DEF_HEAD = re.compile(r"^\s+" + 
        r"((public|private|final|static|synchronized|strictfp)\s+)*" +
        r"(?P<return_value>%s)" % _TYPE +
        r"\s+(?P<method_name>([\w<>]|%[0-9A-F]{2})+)" +
        r"[(](?P<params>(%s|, )*)[)]" % _TYPE +
        r"(\s+throws\s+.+)?"
        r"$")
# _PAT_METHOD_DEF_BEGIN = re.compile(r"^\s+" + r"{" + r"$")
_PAT_METHOD_DEF_END = re.compile(r"^\s+" + r"}" + r"$")

MethodSig = namedtuple("MethodSig", "retv name params")

class MethodData(object):
    def __init__(self, method_sig, scope_class):
        self.method_sig = method_sig
        self.scope_class = scope_class
        self.fields = {}  # name -> str
        self.code = None

    def __repr__(self):
        return "MethodData(%s, %s, *)" % (repr(self.method_sig), repr(self.scope_class))

class ClassData(object):
    def __init__(self, class_name, base_name):
        self.class_name = class_name
        self.base_name = base_name
        self.fields = {}  # name -> str
        self.methods = {}  # MethodSig -> MethodData

    def add_field(self, field_name, field_type):
        self.fields[field_name] = field_type

    def add_method(self, method_sig, method_data):
        self.methods[method_sig] = method_data

    def gen_method(self, method_sig):
        method_data = MethodData(method_sig, self)
        self.methods[method_sig] = method_data
        return method_data

    def __repr__(self):
        return "ClassData(%s, %s, *)" % (repr(self.class_name), repr(self.base_name))

def togd(m):
    if m is None:
        return None
    return m.groupdict()

def parse_jimp_field_decl(entity, linenum, line):
    gd = togd(_PAT_DECL.match(line))
    assert gd
    entity.fields[gd["name"]] = gd["typ"]

def store_jimp_method_code(mtd, linenum, lines):
    mtd.code = (linenum, lines)

def parse_jimp_lines(lines, 
        parse_jimp_class_field_decl=parse_jimp_field_decl, 
        parse_jimp_method_local_decl=parse_jimp_field_decl,
        parse_jimp_method_code=store_jimp_method_code):
    
    class_data_talbe = {}  # name -> classData

    curcls = None
    curmtd = None
    curcode = None
    decl_splitter_appeared = False
    len_lines = len(lines)
    i = 0
    while i < len_lines:
        L = lines[i]; i += 1
        L = L.rstrip()
        gd = togd(_PAT_CLASS_DEF_HEAD.match(L))
        if gd:
            i += 1  # skip class begin line
            curcls = ClassData(gd["class_name"], gd["base_name"])
            class_data_talbe[curcls.class_name] = curcls
            decl_splitter_appeared = False
            continue
        m = _PAT_CLASS_DEF_END.match(L)
        if m:
            curcls = None
            continue
        gd = togd(_PAT_METHOD_DEF_HEAD.match(L))
        if gd:
            i += 1  # skip method begin line
            p =  gd["params"]
            params = p.split(", ") if p else []
            curmtd = curcls.gen_method(MethodSig(gd["return_value"], gd["method_name"], tuple(params)))
            decl_splitter_appeared = False
            continue
        m = _PAT_METHOD_DEF_END.match(L)
        if m:
            assert curcode
            parse_jimp_method_code(curmtd, i - len(curcode), curcode)
            curmtd = None
            continue

        assert not re.match(r"\s*[{}]", L)
        if not L:
            decl_splitter_appeared = True
            if curmtd:
                curcode = []
            continue

        if curmtd:
            if not decl_splitter_appeared:
                parse_jimp_method_local_decl(curmtd, i, L)
            else:
                curcode.append(L)
        elif curcls:
            if not decl_splitter_appeared:
                parse_jimp_class_field_decl(curmtd, i, L)
            else:
                assert False
        else:
            assert False
    return class_data_talbe

def main(argv):
    filename = argv[1]
    lines = list(readline_iter(filename))
    parse_jimp = parse_jimp_lines(lines)
    print parse_jimp

if __name__ == '__main__':
    main(sys.argv)
