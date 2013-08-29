#coding: utf-8

import unittest

import sys
import os.path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))

import jimp_code_body_to_tree_elem as jcbte

def str_to_char_list(s):
    return [c for c in s]

class JimpCodeTransformerTest(unittest.TestCase):
    def test_paths_to_ordred_andor_tree_simple(self):
        paths = map(str_to_char_list, ["123", "12"])
        tree = jcbte.paths_to_ordred_andxor_tree(paths)
        expected = [jcbte.ORDERED_AND, '1', '2', [jcbte.ORDERED_XOR, '3', [jcbte.ORDERED_AND]]]
        self.assertEqual(tree, expected)

    def test_paths_to_ordred_andor_tree_empty(self):
        paths = []
        tree = jcbte.paths_to_ordred_andxor_tree(paths)
        self.assertEqual(tree, [jcbte.ORDERED_AND])

    def test_paths_to_ordred_andor_tree_single(self):
        paths = map(str_to_char_list, ["123"])
        tree = jcbte.paths_to_ordred_andxor_tree(paths)
        self.assertEqual(tree, [jcbte.ORDERED_AND, '1', '2', '3'])

    def test_paths_to_ordred_andor_tree_simple2(self):
        paths = map(str_to_char_list, ["123", "13"])
        tree = jcbte.paths_to_ordred_andxor_tree(paths)
        expected = [jcbte.ORDERED_AND, '1', [jcbte.ORDERED_XOR, '2', [jcbte.ORDERED_AND]], '3']
        self.assertEqual(tree, expected)

    def test_paths_to_ordred_andor_tree_complex(self):
        paths = map(str_to_char_list, ["12345", "135", "123a5"])
        tree = jcbte.paths_to_ordred_andxor_tree(paths)
        expected = [jcbte.ORDERED_AND, '1', [jcbte.ORDERED_XOR, '3', [jcbte.ORDERED_AND, '2', '3', [jcbte.ORDERED_XOR, '4', 'a']]], '5']
        self.assertEqual(tree, expected)

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()