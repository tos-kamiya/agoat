# coding: utf-8

import os
import re
import sys
from collections import namedtuple

from _utilities import readline_iter
from _jimp_code_parser import parse_jimp_code

from _jimp_code_parser import SPECIALINVOKE, INVOKE, RETURN, THROW, IFGOTO, GOTO, SWITCH, LABEL  # re-export

_IDENTIFIER = r"([\w.$]+|'\w+')"
_CLASS = r'class\s+"[\w/$]+"'
_TYPE = r"(([\w.$]|\[|\])+)"
_METHOD_NAME = r"(([\w<>\\])+|access[$]\d+|class[$])"
_ATTR = r"(abstract|public|private|protected|final|static|synchronized|strictfp|transient|volatile|native)"


def is_decl_line(L):
    L = L.strip()
    if not (L and L.endswith(";")):
        return False
    i = L.find(" ")
    if i < 0:
        return False
    f0 = L[:i]
    if f0 in ("if", "goto", "class", "interface", "return", "throw", "catch", "case"):
        return False
    f = L.find
    return f("(") < 0 and f("=") < 0 and f("{") < 0 and f("}") < 0 and f(":") < 0

_PAT_DECL = re.compile(r"^\s+" +
                       r"(%s\s+)*" % _ATTR +
                       r"(enum\s+)?(?P<typ>%s)\s+" % _TYPE +
                       r"(?P<names>(%s|, )+)" % _IDENTIFIER +
                       r";" +
                       r"$")

_PAT_INTERFACE_DEF_HEAD = re.compile(r"^" +
                                     r"(%s\s+)*" % _ATTR +
                                     r"(annotation\s+)?interface\s+(?P<interf_name>%s)" % _IDENTIFIER +
                                     r"(\s+extends\s+(?P<base_names>(%s| |, )+))?" % _IDENTIFIER +
                                     r"$")
# _PAT_INTERFACE_DEF_BEGIN = re.compile("^" + "{" + "$")
_PAT_INTERFACE_DEF_END = re.compile("^" + "}" + "$")

_PAT_CLASS_DEF_HEAD = re.compile(r"^" +
                                 r"(%s\s+)*" % _ATTR +
                                 r"(enum\s+)?class\s+(?P<class_name>%s)" % _IDENTIFIER +
                                 r"(\s+extends\s+(?P<base_name>%s))" % _IDENTIFIER +
                                 r"(\s+implements\s+(?P<interf_names>(%s| |, )+))?" % _IDENTIFIER +
                                 r"$")
# _PAT_CLASS_DEF_BEGIN = re.compile("^" + "{" + "$")
_PAT_CLASS_DEF_END = re.compile("^" + "}" + "$")

_PAT_METHOD_DEF_HEAD = re.compile(r"^\s+" +
                                  r"(%s\s+)*" % _ATTR +
                                  r"(?P<return_value>%s)" % _TYPE +
                                  r"\s+(?P<method_name>%s)" % _METHOD_NAME +
                                  r"[(](?P<params>(%s|, )*)[)]" % _TYPE +
                                  r"(\s+throws\s(?P<thrown_names>(%s| |, )+))?" % _TYPE + 
                                  r"(?P<semicolon>;)?")
# _PAT_METHOD_DEF_BEGIN = re.compile(r"^\s+" + r"{" + r"$")
_PAT_METHOD_DEF_END = re.compile(r"^\s+" + r"}" + r"$")


def _none_to_void(t):
    return t if t is not None else 'void'


def _void_to_none(t):
    return t if t != 'void' else None

def ClzMethodSig(clz, retv, name, params):
    items = [clz, _none_to_void(retv), name]
    items.extend(map(_none_to_void, params))
    return '\t'.join(items)

def clzmsig_clz(clzmsig):
    return clzmsig.split('\t')[0]

def clzmsig_retv(clzmsig):
    return _void_to_none(clzmsig.split('\t')[1])

def clzmsig_method(clzmsig):
    return _void_to_none(clzmsig.split('\t')[2])

def clzmsig_params(clzmsig):
    return tuple(_void_to_none(t) for t in clzmsig.split('\t')[3:])

def clzmsig_to_str(clzmsig):
    return clzmsig

def clzmsig_from_str(s):
    return s

def clzmsig_methodsig(clzmsig):
    return '\t'.join(clzmsig.split('\t')[1:])


class InvalidText(ValueError):
    pass


class MethodData(object):

    def __init__(self, clzmsig, scope_class):
        self.clzmsig = clzmsig
        self.scope_class = scope_class
        self.fields = {}  # name -> str
        self.code = None

    def __repr__(self):
        return "MethodData(%s, %s, *)" % (repr(self.clzmsig), repr(self.scope_class))


class ClassData(object):

    def __init__(self, class_name, base_name, interf_names=None):
        self.class_name = class_name
        self.base_name = base_name
        self.interf_names = interf_names
        self.fields = {}  # name -> str
        self.methods = {}  # ClzMethodSig -> MethodData

    def add_field(self, field_name, field_type):
        self.fields[field_name] = field_type

    def gen_method(self, retv, method, params):
        clzmsig = ClzMethodSig(self.class_name, retv, method, params)
        method_data = MethodData(clzmsig, self)
        self.methods[clzmsig] = method_data
        return method_data

    def __repr__(self):
        return "ClassData(%s, %s, *)" % (repr(self.class_name), repr(self.base_name))


def togd(m):
    if m is None:
        return None
    return m.groupdict()


def parse_jimp_field_decl(entity, linenum, line):
    gd = togd(_PAT_DECL.match(line))
    if not gd:
        raise InvalidText("line %d: invalid field decl" % linenum)
    names = gd["names"].split(", ")
    typ = gd["typ"]
    for name in names:
        entity.fields[name] = typ


def store_jimp_method_code(mtd, line_with_linenums):
    mtd.code = parse_jimp_code(line_with_linenums)


def parse_jimp_lines(lines,
                     trace_invocation_via_interface=True,
                     parse_jimp_class_field_decl=parse_jimp_field_decl,
                     parse_jimp_method_local_decl=parse_jimp_field_decl,
                     parse_jimp_method_code=store_jimp_method_code):

    class_name = None
    class_data = None

    curcls = None
    curmtd = None
    curcode = None
    len_lines = len(lines)
    prev_linenum = -1
    linenum = 0
    while linenum < len_lines:
        assert prev_linenum < linenum
        prev_linenum = linenum
        L = lines[linenum]
        linenum += 1
        L = L.rstrip()
        # sys.stderr.write("L=%s\n" % L)  # debug
        if not L:
            continue

        gd = togd(_PAT_INTERFACE_DEF_HEAD.match(L))
        if gd:
            # treat an interface like an abstract class
            assert class_name is None
            linenum += 1
            class_name = gd["interf_name"]
            t = gd["base_names"]
            base_names = t.split(" ") if t else None
            class_data = curcls = ClassData(class_name, None, base_names)
            if not trace_invocation_via_interface:
                curcls = None
            continue
        gd = togd(_PAT_CLASS_DEF_HEAD.match(L))
        if gd:
            assert class_name is None
            linenum += 1  # skip class begin line
            class_name = gd["class_name"]
            t = gd["interf_names"]
            interf_names = t.split(", ") if t else None
            class_data = curcls = ClassData(class_name, gd["base_name"], interf_names)
            continue
        m = _PAT_CLASS_DEF_END.match(L)
        if m:
            curcls = None
            continue
        gd = togd(_PAT_METHOD_DEF_HEAD.match(L))
        if gd:
            linenum += 1  # skip method begin line
            if curcls:
                p = gd["params"]
                params = p.split(", ") if p else []
                retv = gd["return_value"]
                if retv == "void":
                    retv = None
                curmtd = curcls.gen_method(retv, gd["method_name"], tuple(params))
            curcode = []
            continue
        m = _PAT_METHOD_DEF_END.match(L)
        if m:
            assert curcode
            parse_jimp_method_code(curmtd, curcode)
            curmtd = None
            curcode = []
            continue

        if curmtd:
            if is_decl_line(L):
                parse_jimp_method_local_decl(curmtd, linenum, L)
            else:
                curcode.append((linenum, L))
        elif curcls:
            if is_decl_line(L):
                assert curcls is not None
                parse_jimp_class_field_decl(curcls, linenum, L)
            else:
                raise InvalidText("line %d: invalid line" % linenum)
        else:
            raise InvalidText("line %d: invalid line" % linenum)

    return class_name, class_data


def read_class_table_from_dir_iter(dirname):
    files = sorted(os.listdir(dirname))
    for f in files:
        if f.endswith(".jimp"):
            p = os.path.join(dirname, f)
            lines = list(readline_iter(p))
            r = parse_jimp_lines(lines)
            if r is not None:
                yield r


def main(argv, out=sys.stdout):
    filename = argv[1]
    lines = list(readline_iter(filename))
    parse_jimp = parse_jimp_lines(lines)
    out.write("%s\n" % repr(parse_jimp))

if __name__ == '__main__':
    main(sys.argv)
