#coding: utf-8

import unittest

import sys
import os.path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))

import jimp_code_transformer as jct

def str_to_char_list(s):
    return [c for c in s]

class JimpCodeTransformerTest(unittest.TestCase):
    def test_paths_to_ordred_andor_tree_simple(self):
        paths = map(str_to_char_list, ["123", "12"])
        tree = jct.paths_to_ordred_andor_tree(paths)
        expected = [jct.ORDERED_AND, '1', '2', [jct.ORDERED_OR, [jct.ORDERED_AND], '3']]
        self.assertEqual(tree, expected)

    def test_paths_to_ordred_andor_tree_empty(self):
        paths = []
        tree = jct.paths_to_ordred_andor_tree(paths)
        self.assertEqual(tree, [jct.ORDERED_AND])

    def test_paths_to_ordred_andor_tree_single(self):
        paths = map(str_to_char_list, ["123"])
        tree = jct.paths_to_ordred_andor_tree(paths)
        self.assertEqual(tree, [jct.ORDERED_AND, '1', '2', '3'])

    def test_paths_to_ordred_andor_tree_simple2(self):
        paths = map(str_to_char_list, ["123", "13"])
        tree = jct.paths_to_ordred_andor_tree(paths)
        expected = [jct.ORDERED_AND, '1', [jct.ORDERED_OR, [jct.ORDERED_AND], '2'], '3']
        self.assertEqual(tree, expected)

    def test_paths_to_ordred_andor_tree_complex(self):
        paths = map(str_to_char_list, ["12345", "135", "123a5"])
        tree = jct.paths_to_ordred_andor_tree(paths)
        expected = [jct.ORDERED_AND, '1', [jct.ORDERED_OR, [jct.ORDERED_AND, '2', '3', [jct.ORDERED_OR, '4', 'a']], '3'], '5']
        self.assertEqual(tree, expected)

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()