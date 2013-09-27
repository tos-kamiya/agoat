# coding: utf-8

import re

_IDENTIFIER = r"([\w.$]+|'\w+')"
_METHOD_NAME = r"(([\w<>\\])+|access[$]\d+|class[$])"
_LEFT = r"%s(\[%s\])?" % (_IDENTIFIER, _IDENTIFIER)

_PAT_BIND = re.compile(r"^\s*%s\s*:=\s*@?%s\s*;$" % (_IDENTIFIER, _IDENTIFIER))
_PAT_NEWARRAY = re.compile(r"^\s*%s\s*=\s*newarray\s+.*;$" % _LEFT)
_PAT_NEW = re.compile(r"^\s*%s\s*=\s*new\s+.*;$" % _LEFT)
_PAT_SOME_ASSIGN = re.compile(r"^\s+%s\s*=.*;$" % _LEFT)
_PAT_RETURN = re.compile(r"^\s*return.*;$")
_PAT_THROW = re.compile(r"^\s*throw.*;$")
_PAT_SPECIALINVOKE = re.compile(
    r"^\s*(?P<left>%s)\s*=\s*specialinvoke\s+(?P<receiver>%s)[.](?P<method_name>%s)[(](?P<args>.*)[)]\s*;$" % (_LEFT, _IDENTIFIER, _METHOD_NAME))
_PAT_SPECIALINVOKE_WO_RETURN = re.compile(
    r"^\s*specialinvoke\s+(?P<receiver>%s)[.](?P<method_name>%s)[(](?P<args>.*)[)]\s*;$" % (_IDENTIFIER, _METHOD_NAME))
_PAT_INVOKE = re.compile(
    r"^\s*(?P<left>%s)\s*=\s*(?P<receiver>%s)[.](?P<method_name>%s)[(](?P<args>.*)[)]\s*;$" % (_LEFT, _IDENTIFIER, _METHOD_NAME))
_PAT_INVOKE_WO_RETURN = re.compile(
    r"^\s*(?P<receiver>%s)[.](?P<method_name>%s)[(](?P<args>.*)[)]\s*;$" % (_IDENTIFIER, _METHOD_NAME))
_PAT_IF_GOTO = re.compile(
    r"^\s*if\s+.*goto\s+(?P<label>%s)\s*;$" % _IDENTIFIER)
_PAT_GOTO = re.compile(r"^\s*goto\s+(?P<label>%s)\s*;$" % _IDENTIFIER)
_PAT_LABEL = re.compile(r"^\s*(?P<label>%s):$" % _IDENTIFIER)
_PAT_SWITCH = re.compile(r"^\s*(table|lookup)switch[(].*$")
_PAT_CASE = re.compile(
    r"^\s*case\s+[^:]+:\s+goto\s+(?P<label>%s)\s*;$" % _IDENTIFIER)
_PAT_DEFAULT = re.compile(
    r"^\s*default:\s+goto\s+(?P<label>%s)\s*;$" % _IDENTIFIER)
_PAT_CATCH = re.compile(r"^\s*catch\s+.*;$")

_PAT_STRING_LITERAL = re.compile(r'^"([^"\\]|[\\].)*?"' + '|' + r"^'([^'\\]|[\\].)*?'")


def togd(m):
    if m is None:
        return None
    return m.groupdict()


def parse_args(s):
    items = []
    while s:
        m = _PAT_STRING_LITERAL.match(s)
        if m:
            items.append(m.group(0))
            s = s[m.end():]
            if s.startswith(", "):
                s = s[2:]
        else:
            p = s.find(", ")
            if p >= 0:
                items.append(s[:p])
                s = s[p + 2:]
            else:
                items.append(s)
                s = ''
    return tuple(items)

SPECIALINVOKE = "specialinvoke"
INVOKE = "invoke"
RETURN = "return"
THROW = "throw"
IFGOTO = "ifgoto"
GOTO = "goto"
SWITCH = "switch"
LABEL = "label"


class InvalidCode(ValueError):
    pass


def parse_jimp_code(line_with_linenums, filename=None):
    if filename is not None:
        def loc(linenum):
            return (filename, linenum)
    else:
        def loc(linenum):
            return linenum
    bpats = (_PAT_IF_GOTO, IFGOTO), (_PAT_GOTO, GOTO), (_PAT_LABEL, LABEL)
    inss = []
    len_lines = len(line_with_linenums)
    i = 0
    while i < len_lines:
        linenum, L = line_with_linenums[i]
        if not L:
            i += 1
        elif _PAT_BIND.match(L):
            i += 1
        elif _PAT_NEWARRAY.match(L):
            i += 1
        elif _PAT_NEW.match(L):
            i += 1
        elif _PAT_CATCH.match(L):
            i += 1
        elif _PAT_RETURN.match(L):
            inss.append((RETURN, loc(linenum)))
            i += 1
        elif _PAT_THROW.match(L):
            inss.append((THROW, loc(linenum)))
            i += 1
        else:
            found = False
            for p, cmd in bpats:
                gd = togd(p.match(L))
                if gd:
                    inss.append((cmd, gd["label"], loc(linenum)))
                    i += 1
                    found = True
                    break  # for p, cmd
            if found:
                continue  # while i
            if _PAT_SWITCH.match(L):
                destination_labels = []
                i += 2
                _, L = line_with_linenums[i]
                while True:
                    gd = togd(_PAT_CASE.match(L) or _PAT_DEFAULT.match(L))
                    if not gd:
                        assert re.match("^\s*};$", L)
                        i += 1
                        break
                    destination_labels.append(gd["label"])
                    i += 1
                    _, L = line_with_linenums[i]
                inss.append((SWITCH, tuple(destination_labels), loc(linenum)))
                continue  # while i
            gd = togd(_PAT_SPECIALINVOKE.match(L)
                      or _PAT_SPECIALINVOKE_WO_RETURN.match(L))
            if gd:
                retv = gd["left"] if "left" in gd else None
                argt = parse_args(gd["args"])
                inss.append(
                    (SPECIALINVOKE, gd["receiver"], gd["method_name"], argt, retv, loc(linenum)))
                i += 1
                continue  # while i
            gd = togd(_PAT_INVOKE.match(L) or _PAT_INVOKE_WO_RETURN.match(L))
            if gd:
                retv = gd["left"] if "left" in gd else None
                argt = parse_args(gd["args"])
                inss.append(
                    (INVOKE, gd["receiver"], gd["method_name"], argt, retv, loc(linenum)))
                i += 1
                continue  # while i
            if _PAT_SOME_ASSIGN.match(L):
                i += 1
                pass
            else:
                if filename:
                    raise InvalidCode(
                        "file %s, line %d: invalid syntax" % (filename, linenum))
                else:
                    raise InvalidCode("line %d: invalid syntax" % linenum)
    return inss
