# coding: utf-8

import unittest

import sys
import os.path
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))

import andor_tree_query as atq


class AndOrTreeQueryTest(unittest.TestCase):
    def test_find_lower_bound_nodes_empty_tree(self):
        def pred(node):
            if isinstance(node, list):
                return atq.Undecided
            else:
                return node == 3
        tree = [atq.ORDERED_AND]
        lbns = atq.find_lower_bound_nodes(tree, pred)
        self.assertSequenceEqual(lbns, [])

    def test_find_lower_bound_nodes_single_depth_trees(self):
        def pred(node):
            if isinstance(node, list):
                return atq.Undecided
            else:
                return node == 3
        tree = [atq.ORDERED_OR, 1, 2, 3]
        lbns = atq.find_lower_bound_nodes(tree, pred)
        self.assertSequenceEqual(lbns, [3])

        tree = [atq.ORDERED_OR, 4, 5, 6]
        lbns = atq.find_lower_bound_nodes(tree, pred)
        self.assertSequenceEqual(lbns, [])

        tree = [atq.ORDERED_OR, 2, 3, 4]
        lbns = atq.find_lower_bound_nodes(tree, pred)
        self.assertSequenceEqual(lbns, [3])

        tree = [atq.ORDERED_AND, 2, 3, 4]
        lbns = atq.find_lower_bound_nodes(tree, pred)
        self.assertSequenceEqual(lbns, [3])

        tree = [atq.ORDERED_OR, 1, 2, 3, 1, 2, 3]
        lbns = atq.find_lower_bound_nodes(tree, pred)
        self.assertSequenceEqual(lbns, [3, 3])

    def test_find_lower_bound_nodes_multiple_depth_trees(self):
        def pred(node):
            if isinstance(node, list):
                return atq.Undecided
            else:
                return node == 3
        tree = [atq.ORDERED_OR, 1, 2, [atq.ORDERED_AND, 3]]
        lbns = atq.find_lower_bound_nodes(tree, pred)
        self.assertSequenceEqual(lbns, [3])

        tree = [atq.ORDERED_OR, 4, 5, [atq.ORDERED_AND, 6]]
        lbns = atq.find_lower_bound_nodes(tree, pred)
        self.assertSequenceEqual(lbns, [])

        tree = [atq.ORDERED_OR, 1, 2, [atq.ORDERED_AND, 6]]
        lbns = atq.find_lower_bound_nodes(tree, pred)
        self.assertSequenceEqual(lbns, [])

        tree = [atq.ORDERED_OR, 4, 5, [atq.ORDERED_AND, 3]]
        lbns = atq.find_lower_bound_nodes(tree, pred)
        self.assertSequenceEqual(lbns, [3])

        tree = [atq.ORDERED_OR, 1, 2, [atq.ORDERED_AND, 3], [atq.ORDERED_AND, 3]]
        lbns = atq.find_lower_bound_nodes(tree, pred)
        self.assertSequenceEqual(lbns, [3, 3])

    def test_find_lower_bound_nodes_complex_predicate(self):
        def pred(node):
            if isinstance(node, list) and node and \
                    node[0] == atq.ORDERED_AND and 1 in node and 3 in node:
                return True
            else:
                return atq.Undecided
        tree = [atq.ORDERED_AND, 1, 2, [atq.ORDERED_AND, 3]]
        lbns = atq.find_lower_bound_nodes(tree, pred)
        self.assertSequenceEqual(lbns, [])

        tree = [atq.ORDERED_AND, 1, 2, 3]
        lbns = atq.find_lower_bound_nodes(tree, pred)
        self.assertSequenceEqual(lbns, [[atq.ORDERED_AND, 1, 2, 3]])

        tree = [atq.ORDERED_OR, [atq.ORDERED_AND, 1, 2],  [atq.ORDERED_AND, 1, 2, 3]]
        lbns = atq.find_lower_bound_nodes(tree, pred)
        self.assertSequenceEqual(lbns, [[atq.ORDERED_AND, 1, 2, 3]])

    def test_mark_uncontributing_nodes_empty_tree(self):
        def pred(node):
            if node == 1 or node == 3:
                return True
            else:
                return atq.Undecided
        tree = [atq.ORDERED_AND]
        unm = atq.mark_uncontributing_nodes(tree, pred)
        self.assertEqual(unm, atq.Uncontributing(tree))

    def test_mark_uncontributing_nodes_single_depth_tree(self):
        def pred(node):
            if node == 1 or node == 3:
                return True
            else:
                return atq.Undecided
        tree = [atq.ORDERED_AND, 1, 2, 3]
        unm = atq.mark_uncontributing_nodes(tree, pred)
        self.assertSequenceEqual(unm, [atq.ORDERED_AND, 1, atq.Uncontributing(2), 3])

    def test_mark_uncontributing_nodes_multiple_depth_tree(self):
        def pred(node):
            if node == 1 or node == 3:
                return True
            else:
                return atq.Undecided
        tree = [atq.ORDERED_AND, 1, 2, [atq.ORDERED_OR, 3, 4]]
        unm = atq.mark_uncontributing_nodes(tree, pred)
        self.assertSequenceEqual(unm, [atq.ORDERED_AND, 1, atq.Uncontributing(2), [atq.ORDERED_OR, 3, atq.Uncontributing(4)]])

    def test_path_min_length_empty(self):
        tree = [atq.ORDERED_AND]
        L = atq.path_min_length(tree)
        self.assertEqual(L, 0)

    def test_path_min_length_invalid(self):
        tree = [atq.ORDERED_AND, 1, 2, [atq.ORDERED_OR]]
        with self.assertRaises(atq.LengthNotDefined):
            L = atq.path_min_length(tree)

    def test_path_min_length(self):
        tree = [atq.ORDERED_AND, 1, 2, [atq.ORDERED_OR, 3]]
        L = atq.path_min_length(tree)
        self.assertEqual(L, 3)

        tree = [atq.ORDERED_AND, 1, 2, [atq.ORDERED_OR, 3, [atq.ORDERED_AND, 4, 5]]]
        L = atq.path_min_length(tree)
        self.assertEqual(L, 3)

        tree = [atq.ORDERED_AND, 1, 2, [atq.ORDERED_AND, 3, 4]]
        L = atq.path_min_length(tree)
        self.assertEqual(L, 4)

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
