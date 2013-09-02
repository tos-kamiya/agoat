#coding: utf-8

import unittest

import sys
import os.path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))

import jimp_parser as jp
import jimp_code_body_to_tree_elem as jcbte

def str_to_char_list(s):
    return [c for c in s]

class JimpCodeBodyToTreeElemTest(unittest.TestCase):
#
# these test cases have been removed, because paths_to_ordred_andor_tree function now
# changed its behaviour and not merge paths anymore.
# 
#     def test_paths_to_ordred_andor_tree_simple(self):
#         paths = map(str_to_char_list, ["123", "12"])
#         tree = jcbte.paths_to_ordred_andor_tree(paths, item_types=str)
#         expected = [jcbte.ORDERED_AND, '1', '2', [jcbte.ORDERED_XOR, '3', [jcbte.ORDERED_AND]]]
#         self.assertEqual(tree, expected)
# 
#     def test_paths_to_ordred_andor_tree_empty(self):
#         paths = []
#         tree = jcbte.paths_to_ordred_andor_tree(paths, item_types=str)
#         self.assertEqual(tree, [jcbte.ORDERED_AND])
# 
#     def test_paths_to_ordred_andor_tree_single(self):
#         paths = map(str_to_char_list, ["123"])
#         tree = jcbte.paths_to_ordred_andor_tree(paths, item_types=str)
#         self.assertEqual(tree, [jcbte.ORDERED_AND, '1', '2', '3'])
# 
#     def test_paths_to_ordred_andor_tree_simple2(self):
#         paths = map(str_to_char_list, ["123", "13"])
#         tree = jcbte.paths_to_ordred_andor_tree(paths, item_types=str)
#         expected = [jcbte.ORDERED_AND, '1', [jcbte.ORDERED_XOR, '2', [jcbte.ORDERED_AND]], '3']
#         self.assertEqual(tree, expected)
# 
#     def test_paths_to_ordred_andor_tree_complex(self):
#         paths = map(str_to_char_list, ["12345", "135", "123a5"])
#         tree = jcbte.paths_to_ordred_andor_tree(paths, item_types=str)
#         expected = [jcbte.ORDERED_AND, '1', [jcbte.ORDERED_XOR, '3', [jcbte.ORDERED_AND, '2', '3', [jcbte.ORDERED_XOR, '4', 'a']]], '5']
#         self.assertEqual(tree, expected)
        
    def test_convert_to_execution_paths_ift(self):
        inss = [
            (jp.IFGOTO, 'label0'),
            (jp.INVOKE, 'somemethod'),
            (jp.LABEL, 'label0'),
            (jp.RETURN,)
        ]
        expected_paths = [
            [(jp.INVOKE, 'somemethod'), (jp.LABEL, 'label0'), (jp.RETURN,)], 
            [(jp.LABEL, 'label0'), (jp.RETURN,)]
        ]
        expected_paths.sort()
        paths = jcbte.convert_to_execution_paths(inss)
        paths.sort()
        self.assertSequenceEqual(paths, expected_paths)

    def test_convert_to_execution_paths_ife(self):
        inss = [
            (jp.IFGOTO, 'label0'),
            (jp.GOTO, 'label1'),
            (jp.LABEL, 'label0'),
            (jp.INVOKE, 'somemethod'),
            (jp.LABEL, 'label1'),
            (jp.RETURN,)
        ]
        expected_paths = [
            [(jp.LABEL, 'label0'), (jp.INVOKE, 'somemethod'), (jp.LABEL, 'label1'), (jp.RETURN,)], 
            [(jp.LABEL, 'label1'), (jp.RETURN,)]
        ]
        expected_paths.sort()
        paths = jcbte.convert_to_execution_paths(inss)
        paths.sort()
        self.assertSequenceEqual(paths, expected_paths)

    def test_convert_to_execution_paths_ifte(self):
        inss = [
            (jp.IFGOTO, 'label0'),
            (jp.INVOKE, 'somemethod'),
            (jp.GOTO, 'label1'),
            (jp.LABEL, 'label0'),
            (jp.INVOKE, 'anothermethod'),
            (jp.LABEL, 'label1'),
            (jp.RETURN,)
        ]
        expected_paths = [
            [(jp.LABEL, 'label0'), (jp.INVOKE, 'anothermethod'), (jp.LABEL, 'label1'), (jp.RETURN,)], 
            [(jp.INVOKE, 'somemethod'), (jp.LABEL, 'label1'), (jp.RETURN,)]
        ]
        expected_paths.sort()
        paths = jcbte.convert_to_execution_paths(inss)
        paths.sort()
        self.assertSequenceEqual(paths, expected_paths)
        
    def test_convert_to_execution_paths_switch(self):
        inss = [
            (jp.SWITCH, ['label1', 'label2', 'label3', 'label4', 'label5']),
            (jp.LABEL, 'label1'),
            (jp.GOTO, 'label5'),
            (jp.LABEL, 'label2'),
            (jp.INVOKE, 'method2'),
            (jp.GOTO, 'label5'),
            (jp.LABEL, 'label3'),
            (jp.INVOKE, 'method3'),
            (jp.GOTO, 'label5'),
            (jp.LABEL, 'label4'),
            (jp.INVOKE, 'method4'),
            (jp.LABEL, 'label5'),
            (jp.RETURN,)
        ]
        expected_paths = [
            [(jp.LABEL, 'label1'), (jp.LABEL, 'label5'), (jp.RETURN,)],
            [(jp.LABEL, 'label2'), (jp.INVOKE, 'method2'), (jp.LABEL, 'label5'), (jp.RETURN,)], 
            [(jp.LABEL, 'label3'), (jp.INVOKE, 'method3'), (jp.LABEL, 'label5'), (jp.RETURN,)], 
            [(jp.LABEL, 'label4'), (jp.INVOKE, 'method4'), (jp.LABEL, 'label5'), (jp.RETURN,)], 
            [(jp.LABEL, 'label5'), (jp.RETURN,)] 
        ]
        expected_paths.sort()
        paths = jcbte.convert_to_execution_paths(inss)
        paths.sort()
        self.assertSequenceEqual(paths, expected_paths)

    def test_convert_to_execution_paths_loop(self):
        inss = [
            (jp.LABEL, 'label0'),
            (jp.IFGOTO, 'label1'),
            (jp.INVOKE, 'somemethod'),
            (jp.GOTO, 'label0'),
            (jp.LABEL, 'label1'),
            (jp.INVOKE, 'anothermethod'),
            (jp.RETURN,)
        ]
        expected_paths = [
            [(jp.LABEL, 'label0'), (jp.LABEL, 'label1'), (jp.INVOKE, 'anothermethod'), (jp.RETURN,) ],
            [(jp.LABEL, 'label0'), (jp.INVOKE, 'somemethod'), (jp.LABEL, 'label1'), (jp.INVOKE, 'anothermethod'), (jp.RETURN,)]
        ]
        expected_paths.sort()
        paths = jcbte.convert_to_execution_paths(inss)
        paths.sort()
        self.assertSequenceEqual(paths, expected_paths)

    def test_get_max_branches_of_boxes(self):
        inss = [
            (jp.INVOKE, "println"),
            (jp.LABEL, 'label0'),
            (jp.INVOKE, "println"),
            (jp.IFGOTO, 'label0')
        ]
        c = jcbte.get_max_branches_of_boxes(inss)

        self.assertEqual(c, 1)
        inss = [
            (jp.INVOKE, "println"),
            (jp.LABEL, 'label0'),
            (jp.INVOKE, "println"),
            [jcbte.BOX,
                (jp.LABEL, 'label1'),
                (jp.INVOKE, "println"),
                (jp.IFGOTO, 'label1'),
                (jp.LABEL, 'label2'),
                (jp.INVOKE, "println"),
                (jp.IFGOTO, 'label2')
              ],
            (jp.IFGOTO, 'label0')
        ]
        c = jcbte.get_max_branches_of_boxes(inss)
        self.assertEqual(c, 2)

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()