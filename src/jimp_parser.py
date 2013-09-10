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
_METHOD_NAME = r"(([\w<>]|%[0-9A-F]{2})+|access[$]\d+|class[$])"
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
                                     r".*$")
# _PAT_INTERFACE_DEF_BEGIN = re.compile("^" + "{" + "$")
_PAT_INTERFACE_DEF_END = re.compile("^" + "}" + "$")

_PAT_CLASS_DEF_HEAD = re.compile(r"^" +
                                 r"(%s\s+)*" % _ATTR +
                                 r"(enum\s+)?class\s+(?P<class_name>%s)" % _IDENTIFIER +
                                 r"(\s+extends\s+(?P<base_name>%s))" % _IDENTIFIER +
                                 r"(\s+implements\s+(?P<interf_names>(%s|, )+))?" % _IDENTIFIER +
                                 r"$")
# _PAT_CLASS_DEF_BEGIN = re.compile("^" + "{" + "$")
_PAT_CLASS_DEF_END = re.compile("^" + "}" + "$")

_PAT_METHOD_DEF_HEAD = re.compile(r"^\s+" +
                                  r"(%s\s+)*" % _ATTR +
                                  r"(?P<return_value>%s)" % _TYPE +
                                  r"\s+(?P<method_name>%s)" % _METHOD_NAME +
                                  r"[(](?P<params>(%s|, )*)[)]" % _TYPE +
                                  r"(\s+throws\s+.+)?")
# _PAT_METHOD_DEF_BEGIN = re.compile(r"^\s+" + r"{" + r"$")
_PAT_METHOD_DEF_END = re.compile(r"^\s+" + r"}" + r"$")


def _none_to_void(t):
    return t if t is not None else 'void'


def _void_to_none(t):
    return t if t is not 'void' else None

if False:
    MethodSig = namedtuple('MethodSig', 'retv name params')

    def methodsig_retv(msig):
        return msig.retv

    def methodsig_name(msig):
        return msig.name

    def methodsig_params(msig):
        return msig.params

    def methodsig_to_str(msig):
        return '%s\t%s\t%s' % (msig.retv, msig.name, '\t'.join(msig.params))

    def methodsig_from_str(s):
        fs = s.split('\t')
        return MethodSig(fs[0], fs[1], tuple(fs[2:]))
else:
    def MethodSig(retv, name, params):
        items = [_none_to_void(retv), name]
        items.extend(map(_none_to_void, params))
        return '\t'.join(items)

    def methodsig_retv(msig):
        return _void_to_none(msig.split('\t')[0])

    def methodsig_name(msig):
        return _void_to_none(msig.split('\t')[1])

    def methodsig_params(msig):
        return tuple(_void_to_none(t) for t in msig.split('\t')[2:])

    def methodsig_to_str(msig):
        return msig

    def methodsig_from_str(s):
        return s


class InvalidText(ValueError):
    pass


class MethodData(object):

    def __init__(self, method_sig, scope_class):
        self.method_sig = method_sig
        self.scope_class = scope_class
        self.fields = {}  # name -> str
        self.code = None

    def __repr__(self):
        return "MethodData(%s, %s, *)" % (repr(self.method_sig), repr(self.scope_class))


class ClassData(object):

    def __init__(self, class_name, base_name, interf_names=None):
        self.class_name = class_name
        self.base_name = base_name
        self.interf_names = interf_names
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
    if not gd:
        assert False
        raise InvalidText("line %d: invalid field decl" % linenum)
    names = gd["names"].split(", ")
    typ = gd["typ"]
    for name in names:
        entity.fields[name] = typ


def store_jimp_method_code(mtd, line_with_linenums):
    mtd.code = parse_jimp_code(line_with_linenums)


def parse_jimp_lines(lines,
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

        if _PAT_INTERFACE_DEF_HEAD.match(L):
            return None

        gd = togd(_PAT_CLASS_DEF_HEAD.match(L))
        if gd:
            assert class_name is None
            linenum += 1  # skip class begin line
            class_name = gd["class_name"]
            t = gd["interf_names"]
            interf_names = t.split(", ") if t else None
            class_data = curcls = ClassData(
                class_name, gd["base_name"], interf_names)
            continue
        m = _PAT_CLASS_DEF_END.match(L)
        if m:
            curcls = None
            continue
        gd = togd(_PAT_METHOD_DEF_HEAD.match(L))
        if gd:
            linenum += 1  # skip method begin line
            p = gd["params"]
            params = p.split(", ") if p else []
            retv = gd["return_value"]
            if retv == "void":
                retv = None
            curmtd = curcls.gen_method(
                MethodSig(retv, gd["method_name"], tuple(params)))
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

    # remove the methods that is declared but does not have body
    empty_methods = [
        msig for msig, md in class_data.methods.iteritems() if md.code is None]
    for msig in empty_methods:
        del class_data.methods[msig]

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
