# coding: utf-8

import unittest

import sys
import os.path
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))

import jimp_parser as jp
import _jimp_code_box_generator as jcbg


def str_to_char_list(s):
    return [c for c in s]


class JimpCodeBoxGeneratorTest(unittest.TestCase):

    def test_make_boxs_nested_loop(self):
        inss = [
            (jp.LABEL, 'label0'),
            (jp.IFGOTO, 'label4'),
            (jp.LABEL, 'label1'),
            (jp.IFGOTO, 'label3'),
            (jp.IFGOTO, 'label2'),
            (jp.INVOKE, 'format'),
            (jp.GOTO, 'label1'),
            (jp.LABEL, 'label2'),
            (jp.GOTO, 'label1'),
            (jp.LABEL, 'label3'),
            (jp.GOTO, 'label0'),
            (jp.LABEL, 'label4'),
            (jp.RETURN,)
        ]
        expected_boxes = [
            [jcbg.BOX,
                (jp.LABEL, 'label0'),
                (jp.IFGOTO, 'label4'),
                [jcbg.BOX,
                    (jp.LABEL, 'label1'),
                    (jp.IFGOTO, 'label3'),
                    (jp.IFGOTO, 'label2'),
                    (jp.INVOKE, 'format'),
                    (jp.GOTO, 'label1'),
                    (jp.LABEL, 'label2'),
                    (jp.GOTO, 'label1'),
                    (jp.LABEL, 'label3')
                 ],
                (jp.GOTO, 'label0'),
                (jp.LABEL, 'label4')
             ],
            (jp.RETURN,)
        ]
        boxed_inss = jcbg.make_boxes(inss)
        self.assertEqual(boxed_inss, expected_boxes)

    def test_make_boxs_if_statements(self):
        inss = [
            (jp.IFGOTO, 'label1'),
            (jp.INVOKE, 'equals'),
            (jp.IFGOTO, 'label0'),
            (jp.INVOKE, 'equals'),
            (jp.IFGOTO, 'label1'),
            (jp.LABEL, 'label0'),
            (jp.INVOKE, 'println'),
            (jp.INVOKE, 'exit'),
            (jp.LABEL, 'label1'),
            (jp.IFGOTO, 'label2'),
            (jp.INVOKE, 'println'),
            (jp.INVOKE, 'exit'),
            (jp.LABEL, 'label2'),
            (jp.INVOKE, 'println'),
            (jp.RETURN,)
        ]
        expected_boxes = [
            [jcbg.BOX,
                (jp.IFGOTO, 'label1'),
                (jp.INVOKE, 'equals'),
                (jp.IFGOTO, 'label0'),
                (jp.INVOKE, 'equals'),
                (jp.IFGOTO, 'label1'),
                (jp.LABEL, 'label0'),
                (jp.INVOKE, 'println'),
                (jp.INVOKE, 'exit'),
                (jp.LABEL, 'label1')
             ],
            [jcbg.BOX,
                (jp.IFGOTO, 'label2'),
                (jp.INVOKE, 'println'),
                (jp.INVOKE, 'exit'),
                (jp.LABEL, 'label2')
             ],
            (jp.INVOKE, 'println'),
            (jp.RETURN,)
        ]
        boxed_inss = jcbg.make_boxes(inss)
        self.assertEqual(boxed_inss, expected_boxes)

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
