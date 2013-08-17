#coding: utf-8

import unittest

import sys
import os.path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))

import andor_tree as at

SameAsInput = object()

class AndOrTreeTest(unittest.TestCase):
    def normalize_testing(self, input_tree, expected=SameAsInput):
        tree = input_tree[:]
        normalized = at.normalize_tree(tree[:])
        assert tree == input_tree
        if expected is SameAsInput:
            expected = input_tree
        self.assertEqual(normalized, expected)

    def test_normalize_tree_len0(self):
        self.normalize_testing([at.ORDERED_AND], SameAsInput)
        self.normalize_testing([at.ORDERED_OR], SameAsInput)

    def test_normalize_tree_len1(self):
        self.normalize_testing([at.ORDERED_AND, 'a'], 'a')
        self.normalize_testing([at.ORDERED_OR, 'a'], 'a')

    def test_normalize_tree_len2(self):
        self.normalize_testing([at.ORDERED_AND, 'b', 'a'], SameAsInput)
        self.normalize_testing([at.ORDERED_OR, 'b', 'a'], [at.ORDERED_OR, 'a', 'b'])

    def test_normalize_tree_len2_dup(self):
        self.normalize_testing([at.ORDERED_AND, 'a', 'a'], SameAsInput)
        self.normalize_testing([at.ORDERED_OR, 'a', 'a'], 'a')

    def test_normalize_tree_dep2_len0_len1(self):
        self.normalize_testing([at.ORDERED_AND, [at.ORDERED_AND, 'b']], 'b')
        self.normalize_testing([at.ORDERED_AND, [at.ORDERED_OR, 'b']], 'b')
        self.normalize_testing([at.ORDERED_OR, [at.ORDERED_AND, 'b']], 'b')
        self.normalize_testing([at.ORDERED_OR, [at.ORDERED_OR, 'b']], 'b')

    def test_normalize_tree_dep2_len1_len1(self):
        self.normalize_testing([at.ORDERED_AND, 'a', [at.ORDERED_AND, 'b']], [at.ORDERED_AND, 'a', 'b'])
        self.normalize_testing([at.ORDERED_AND, 'a', [at.ORDERED_OR, 'b']], [at.ORDERED_AND, 'a', 'b'])
        self.normalize_testing([at.ORDERED_OR, 'a', [at.ORDERED_AND, 'b']], [at.ORDERED_OR, 'a', 'b'])
        self.normalize_testing([at.ORDERED_OR, 'a', [at.ORDERED_OR, 'b']], [at.ORDERED_OR, 'a', 'b'])

    def test_normalize_tree_dep2_len1_len0(self):
        self.normalize_testing([at.ORDERED_AND, 'a', [at.ORDERED_AND]], 'a')
        self.normalize_testing([at.ORDERED_AND, 'a', [at.ORDERED_OR]], [at.ORDERED_OR])
        self.normalize_testing([at.ORDERED_OR, 'a', [at.ORDERED_AND]], SameAsInput)
        self.normalize_testing([at.ORDERED_OR, 'a', [at.ORDERED_OR]], 'a')

    def test_normalize_tree_of_various_item_type(self):
        for item in ('a', 1, None, (), [], (1,), [1]):
            self.normalize_testing([at.ORDERED_AND, item, [at.ORDERED_AND]], item)
            self.normalize_testing([at.ORDERED_AND, item, [at.ORDERED_OR]], [at.ORDERED_OR])
            self.normalize_testing([at.ORDERED_OR, item, [at.ORDERED_AND]], SameAsInput)
            self.normalize_testing([at.ORDERED_OR, item, [at.ORDERED_OR]], item)

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()