#coding: utf-8

import re

_IDENTIFIER = "[\w.$]+"
_TYPE = r"([\w.$]|\[|\])+"
_METHOD_NAME = r"([\w<>]|%[0-9A-F]{2})+"

_PAT_BIND = re.compile(r"^\s*%s\s*:=\s*@?%s\s*;$" % (_IDENTIFIER, _IDENTIFIER))
_PAT_NEWARRAY = re.compile(r"^\s*%s\s*=\s*newarray\s+.*;$" % _IDENTIFIER)
_PAT_NEW = re.compile(r"^\s*%s\s*=\s*new\s+.*;$" % _IDENTIFIER)
_PAT_SOME_ASSIGN = re.compile(r"^\s+%s\s*=.*;$" % _IDENTIFIER)
_PAT_RETURN = re.compile(r"^\s*return.*;$")
_PAT_THROW = re.compile(r"^\s*throw.*;$")
_PAT_SPECIALINVOKE = re.compile(r"^\s*(?P<left>%s)\s*=\s*specialinvoke\s+%s[.](?P<method_name>%s)[(](?P<args>[^)]*)[)]\s*;$" % (_IDENTIFIER, _IDENTIFIER, _METHOD_NAME))
_PAT_SPECIALINVOKE_WO_RETURN = re.compile(r"^\s*specialinvoke\s+%s[.](?P<method_name>%s)[(](?P<args>[^)]*)[)]\s*;$" % (_IDENTIFIER, _METHOD_NAME))
_PAT_INVOKE = re.compile(r"^\s*(?P<left>%s)\s*=\s*(?P<receiver>%s)[.](?P<method_name>%s)[(](?P<args>[^)]*)[)]\s*;$" % (_IDENTIFIER, _IDENTIFIER, _METHOD_NAME))
_PAT_INVOKE_WO_RETURN = re.compile(r"^\s*(?P<receiver>%s)[.](?P<method_name>%s)[(](?P<args>[^)]*)[)]\s*;$" % (_IDENTIFIER, _METHOD_NAME))
_PAT_IF_GOTO = re.compile(r"^\s*if\s+.*goto\s+(?P<label>%s)\s*;$" % _IDENTIFIER)
_PAT_GOTO = re.compile(r"^\s*goto\s+(?P<label>%s)\s*;$" % _IDENTIFIER)
_PAT_LABEL = re.compile(r"^\s*(?P<label>%s):$" % _IDENTIFIER)

_PAT_STRING_LITERAL = re.compile(r'^"([^\"]|\.)*?"' + '|' + r"^'([^\"]|\.)*?'")

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
    return items

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

def parse_jimp_code(linenum, lines):
    bpats = (_PAT_IF_GOTO, IFGOTO), (_PAT_GOTO, GOTO), (_PAT_LABEL, LABEL)
    inss = []
    len_lines = len(lines)
    i = 0
    while i < len_lines:
        L = lines[i]
        if _PAT_BIND.match(L) or _PAT_NEWARRAY.match(L) or _PAT_NEW.match(L):
            i += 1
        elif _PAT_RETURN.match(L):
            inss.append((RETURN,))
            i += 1
        elif _PAT_THROW.match(L):
            inss.append((THROW,))
            i += 1
        else:
            found = False
            for p, cmd in bpats:
                gd = togd(p.match(L))
                if gd:
                    inss.append((cmd, gd["label"]))
                    i += 1
                    found = True
                    break  # for p, cmd
            if found:
                continue
            gd = togd(_PAT_SPECIALINVOKE.match(L) or _PAT_SPECIALINVOKE_WO_RETURN.match(L))
            if gd:
                retv = gd["left"] if "left" in gd else None
                argt = parse_args(gd["args"])
                inss.append((SPECIALINVOKE, None, gd["method_name"], argt, retv))
                i += 1
                continue
            gd = togd(_PAT_INVOKE.match(L) or _PAT_INVOKE_WO_RETURN.match(L))
            if gd:
                retv = gd["left"] if "left" in gd else None
                argt = parse_args(gd["args"])
                inss.append((INVOKE, gd["receiver"], gd["method_name"], argt, retv))
                i += 1
                continue
            if _PAT_SOME_ASSIGN.match(L):
                i += 1
                pass
            else:
                raise InvalidCode("line %d: invalid syntax" % (linenum + i))
    return inss
