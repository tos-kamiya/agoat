#coding: utf-8

import unittest

import sys
import os.path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))

import jimp_code_parser as jcp

helloJimpText = """
public class Hello extends java.lang.Object
{

    public void <init>()
    {
        Hello r0;

        r0 := @this;
        specialinvoke r0.<init>();
        return;
    }

    public static void main(java.lang.String[])
    {
        java.lang.String[] r0;
        java.io.PrintStream $r1;
        java.lang.Object[] $r2;

        r0 := @parameter0;
        $r1 = java.lang.System.out;
        $r2 = newarray (java.lang.Object)[0];
        $r1.format("Hello\n", $r2);
        return;
    }
}
"""

class JimpCodeParserTest(unittest.TestCase):
    def test_special_invoke(self):
        lines = filter(None, r"""
        r0 := @this;
        specialinvoke r0.<init>();
        return;
"""[1:].split("\n"))
        c = jcp.parse_jimp_code(1, lines)
        self.assertSequenceEqual(c, [(jcp.SPECIALINVOKE, None, '<init>', [], None), (jcp.RETURN,)])

    def test_invoke(self):
        lines = filter(None, r"""
        r0 := @parameter0;
        $r1 = java.lang.System.out;
        $r2 = newarray (java.lang.Object)[0];
        $r1.format("Hello\n", $r2);
        return;
"""[1:].split("\n"))
        c = jcp.parse_jimp_code(1, lines)
        self.assertSequenceEqual(c, [(jcp.INVOKE, '$r1', 'format', ['"Hello\\n"', '$r2'], None), (jcp.RETURN,)])

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()