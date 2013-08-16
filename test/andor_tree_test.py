#coding: utf-8

import unittest

import sys
import os.path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))

import andor_tree as at

class AndOrTreeTest(unittest.TestCase):
    def test_normalize_tree_len0(self):
        tree = [at.ORDERED_AND]
        expected = tree[:]
        nt = at.normalize_tree(tree)
        self.assertSequenceEqual(nt, expected)

        tree = [at.ORDERED_OR]
        expected = tree[:]
        nt = at.normalize_tree(tree)
        self.assertSequenceEqual(nt, expected)

    def test_normalize_tree_len1(self):
        tree = [at.ORDERED_AND, 'a']
        expected = 'a'
        self.assertSequenceEqual(at.normalize_tree(tree), expected)

        tree = [at.ORDERED_OR, 'a']
        expected = 'a'
        self.assertSequenceEqual(at.normalize_tree(tree), expected)

    def test_normalize_tree_len2(self):
        tree = [at.ORDERED_AND, 'b', 'a']
        expected = tree[:]
        self.assertSequenceEqual(at.normalize_tree(tree), expected)

        tree = [at.ORDERED_OR, 'b', 'a']
        expected = [at.ORDERED_OR, 'a', 'b']
        self.assertSequenceEqual(at.normalize_tree(tree), expected)

    def test_normalize_tree_len2_dup(self):
        tree = [at.ORDERED_AND, 'a', 'a']
        expected = tree[:]
        self.assertSequenceEqual(at.normalize_tree(tree), expected)

        tree = [at.ORDERED_OR, 'a', 'a']
        expected = 'a'
        self.assertSequenceEqual(at.normalize_tree(tree), expected)

    def test_normalize_tree_dep2_len0_len1(self):
        tree = [at.ORDERED_AND, [at.ORDERED_AND, 'b']]
        expected = 'b'
        self.assertSequenceEqual(at.normalize_tree(tree), expected)

        tree = [at.ORDERED_OR, [at.ORDERED_OR, 'b']]
        expected = 'b'
        self.assertSequenceEqual(at.normalize_tree(tree), expected)

        tree = [at.ORDERED_AND, [at.ORDERED_OR, 'b']]
        expected = 'b'
        self.assertSequenceEqual(at.normalize_tree(tree), expected)

        tree = [at.ORDERED_OR, [at.ORDERED_AND, 'b']]
        expected = 'b'
        self.assertSequenceEqual(at.normalize_tree(tree), expected)

    def test_normalize_tree_dep2_len1_len1(self):
        tree = [at.ORDERED_AND, 'a', [at.ORDERED_AND, 'b']]
        expected = [at.ORDERED_AND, 'a', 'b']
        self.assertSequenceEqual(at.normalize_tree(tree), expected)

        tree = [at.ORDERED_OR, 'a', [at.ORDERED_OR, 'b']]
        expected = [at.ORDERED_OR, 'a', 'b']
        self.assertSequenceEqual(at.normalize_tree(tree), expected)

        tree = [at.ORDERED_AND, 'a', [at.ORDERED_OR, 'b']]
        expected = [at.ORDERED_AND, 'a', 'b']
        self.assertSequenceEqual(at.normalize_tree(tree), expected)

        tree = [at.ORDERED_OR, 'a', [at.ORDERED_AND, 'b']]
        expected = [at.ORDERED_OR, 'a', 'b']
        self.assertSequenceEqual(at.normalize_tree(tree), expected)

    def test_normalize_tree_dep2_len1_len0(self):
        tree = [at.ORDERED_AND, 'a', [at.ORDERED_AND]]
        expected = 'a'
        self.assertSequenceEqual(at.normalize_tree(tree), expected)

        tree = [at.ORDERED_OR, 'a', [at.ORDERED_OR]]
        expected = 'a'
        self.assertSequenceEqual(at.normalize_tree(tree), expected)

        tree = [at.ORDERED_AND, 'a', [at.ORDERED_OR]]
        expected = [at.ORDERED_OR]
        self.assertSequenceEqual(at.normalize_tree(tree), expected)

        tree = [at.ORDERED_OR, 'a', [at.ORDERED_AND]]
        expected = [at.ORDERED_OR, [at.ORDERED_AND], 'a']
        self.assertSequenceEqual(at.normalize_tree(tree), expected)

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()