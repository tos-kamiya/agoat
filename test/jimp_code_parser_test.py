#coding: utf-8

import unittest

import sys
import os.path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))

import _jimp_code_parser as jcp

class JimpCodeParserTest(unittest.TestCase):
    def assert_having_filename(self, c, filename):
        for ins in c:
            loc = ins[-1]
            self.assertEqual(loc[0], filename)

    def test_special_invoke(self):
        lines = filter(None, r"""
        r0 := @this;
        specialinvoke r0.<init>();
        return;
""".split("\n"))
        c = jcp.parse_jimp_code(1, lines)
        self.assertSequenceEqual(c, [
            (jcp.SPECIALINVOKE, 'r0', '<init>', (), None, 2), 
            (jcp.RETURN, 3)
        ])

        fn = "SpecialInvoke.jimp"
        c = jcp.parse_jimp_code(1, lines, fn)
        self.assert_having_filename(c, fn)

    def test_invoke(self):
        lines = filter(None, r"""
        r0 := @parameter0;
        $r1 = java.lang.System.out;
        $r2 = newarray (java.lang.Object)[0];
        $r1.format("Hello\n", $r2);
        return;
""".split("\n"))
        c = jcp.parse_jimp_code(1, lines)
        self.assertSequenceEqual(c, [
            (jcp.INVOKE, '$r1', 'format', ('"Hello\\n"', '$r2'), None, 4), 
            (jcp.RETURN, 5)
        ])

        fn = "Invoke.jimp"
        c = jcp.parse_jimp_code(1, lines, fn)
        self.assert_having_filename(c, fn)

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
            (jcp.IFGOTO, 'label0', 3), 
            (jcp.INVOKE, '$r1', 'println', ('"> got some args..."', ), None, 5),
            (jcp.GOTO, 'label1', 6), 
            (jcp.LABEL, 'label0', 7),
            (jcp.INVOKE, '$r1', 'println', ('"> got no arg"', ), None, 8),
            (jcp.LABEL, 'label1', 9),
            (jcp.RETURN, 10)
        ])
    

        fn = "IfGoto.jimp"
        c = jcp.parse_jimp_code(1, lines, fn)
        self.assert_having_filename(c, fn)

    def test_switch(self):
        lines = filter(None, r"""
        tableswitch($i1)
        {
            case 0: goto label1;
            case 1: goto label2;
            case 2: goto label3;
            case 3: goto label4;
            default: goto label5;
        };
     label1:
        goto label5;
     label2:
        $r17 = java.lang.System.out;
        $r17.println("Hello 1");
        goto label5;
     label3:
        $r17 = java.lang.System.out;
        $r17.println("Hello 2");
        goto label5;
     label4:
        $r17 = java.lang.System.out;
        $r17.println("Hello 3");
     label5:
        return;
""".split("\n"))
        expected = [
            (jcp.SWITCH, ('label1', 'label2', 'label3', 'label4', 'label5'), 1),
            (jcp.LABEL, 'label1', 9), 
            (jcp.GOTO, 'label5', 10), 
            (jcp.LABEL, 'label2', 11), 
            (jcp.INVOKE, '$r17', 'println', ('"Hello 1"', ), None, 13), 
            (jcp.GOTO, 'label5', 14), 
            (jcp.LABEL, 'label3', 15), 
            (jcp.INVOKE, '$r17', 'println', ('"Hello 2"', ), None, 17), 
            (jcp.GOTO, 'label5', 18), 
            (jcp.LABEL, 'label4', 19),
            (jcp.INVOKE, '$r17', 'println', ('"Hello 3"', ), None, 21), 
            (jcp.LABEL, 'label5', 22), 
            (jcp.RETURN, 23)
        ]
        c = jcp.parse_jimp_code(1, lines)
        self.assertSequenceEqual(c, expected)

        offset = 102
        c = jcp.parse_jimp_code(1 + offset, lines)
        self.assertSequenceEqual(c, [ins[:-1] + (ins[-1] + offset,) for ins in expected])
        
        fn = "Switch.jimp"
        c = jcp.parse_jimp_code(1, lines, fn)
        self.assert_having_filename(c, fn)

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()