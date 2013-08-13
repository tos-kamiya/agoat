#coding: utf-8

import unittest

import sys
import os.path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))

import jimp_code_parser as jcp

class JimpCodeParserTest(unittest.TestCase):
    def test_special_invoke(self):
        lines = filter(None, r"""
        r0 := @this;
        specialinvoke r0.<init>();
        return;
""".split("\n"))
        c = jcp.parse_jimp_code(1, lines)
        self.assertSequenceEqual(c, [(jcp.SPECIALINVOKE, None, '<init>', [], None), (jcp.RETURN,)])

    def test_invoke(self):
        lines = filter(None, r"""
        r0 := @parameter0;
        $r1 = java.lang.System.out;
        $r2 = newarray (java.lang.Object)[0];
        $r1.format("Hello\n", $r2);
        return;
""".split("\n"))
        c = jcp.parse_jimp_code(1, lines)
        self.assertSequenceEqual(c, [(jcp.INVOKE, '$r1', 'format', ['"Hello\\n"', '$r2'], None), (jcp.RETURN,)])

    def test_if_goto(self):
        lines = filter(None, r"""
        r0 := @parameter0;
        $i0 = lengthof r0;
        if $i0 < 1 goto label0;
        $r1 = java.lang.System.err;
        $r1.println("> got some args...");
        goto label1;
    label0:
        $r1.println("> got no arg");
    label1:
        return;
""".split("\n"))
        c = jcp.parse_jimp_code(1, lines)
        self.assertSequenceEqual(c, [
            (jcp.IFGOTO, 'label0'), 
            (jcp.INVOKE, '$r1', 'println', ['"> got some args..."'], None),
            (jcp.GOTO, 'label1'), 
            (jcp.LABEL, 'label0'),
            (jcp.INVOKE, '$r1', 'println', ['"> got no arg"'], None),
            (jcp.LABEL, 'label1'),
            (jcp.RETURN,)
        ])

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()