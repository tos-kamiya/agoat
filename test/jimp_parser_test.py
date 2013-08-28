#coding: utf-8

import unittest

import sys
import os.path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))

import jimp_parser as jp

helloJimpText = r"""
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

def stub_store_jimp_method_code(mtd, linenum, lines):
    mtd.code = (linenum, lines)

class JimpParserTest(unittest.TestCase):
    def test_method_sig(self):
        msig = jp.MethodSig("int", "hoge", ())
        self.assertEqual(jp.methodsig_retv(msig), "int")
        self.assertEqual(jp.methodsig_name(msig), "hoge")
        self.assertEqual(jp.methodsig_params(msig), ())
        
    def test_hello_string(self):
        class_name, class_data = jp.parse_jimp_lines(helloJimpText.splitlines(), 
                parse_jimp_method_code=stub_store_jimp_method_code)
        self.assertEqual(class_name, "Hello")
        self.assertEqual(class_data.base_name, "java.lang.Object")
        for msig, m in class_data.methods.iteritems():
            self.assertIn(msig, [jp.MethodSig(None, "<init>", ()), jp.MethodSig(None, "main", ("java.lang.String[]", ))])

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()