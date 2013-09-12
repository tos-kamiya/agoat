# coding: utf-8

import unittest

import re

import sys
import os.path
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))

import calltree as ct
import calltree_query as cq

def new_invoked(clz, msig):
    return (clz, msig, (), None, None)

def new_callnode(clz, msig, body):
    return ct.CallNode((clz, msig, (), None, None), None, body)

A_CALL_TREE = new_callnode("A", "a", 
    [ct.ORDERED_AND,
        new_invoked("B", "b"),
        new_callnode("C", "c",
            [ct.ORDERED_OR,
                new_invoked("D", "d"),
                new_invoked("E", "e"),
            ]
        ),
        new_callnode("F", "f",
            [ct.ORDERED_AND,
                new_invoked("G", "g"),
                new_callnode("H", "h",
                    [ct.ORDERED_AND,
                    ]
                )
            ]
        )
    ]
)


def A_PREDICATE(call_node):
    return call_node.invoked[0] in ('A', 'B', 'C', 'F')


class CalltreeQueryTest(unittest.TestCase):

    def test_missing_query_patterns_of_methods(self):
        qp = [cq.QueryPattern(cq.TARGET_METHOD, "w", re.compile("w")), cq.QueryPattern(cq.TARGET_METHOD, "x", re.compile("x"))]
        summary = []
        missings = cq.missing_query_patterns(summary, qp)
        self.assertEqual(len(missings), 2)
        self.assertEqual(missings[0].word, "w")
        self.assertEqual(missings[1].word, "x")
        
        summary = [("AClass", "void\tsomeMehtod")]
        missings = cq.missing_query_patterns(summary, qp)
        self.assertEqual(len(missings), 2)
        self.assertEqual(missings[0].word, "w")
        self.assertEqual(missings[1].word, "x")

        summary = [("A", "w")]
        missings = cq.missing_query_patterns(summary, qp)
        self.assertEqual(len(missings), 1)
        self.assertEqual(missings[0].word, "x")

        summary = [("B", "x")]
        missings = cq.missing_query_patterns(summary, qp)
        self.assertEqual(len(missings), 1)
        self.assertEqual(missings[0].word, "w")

        summary = [("A", "w"), ("B", "x")]
        missings = cq.missing_query_patterns(summary, qp)
        self.assertEqual(len(missings), 0)

        summary = ['"w x someliteral string"']
        missings = cq.missing_query_patterns(summary, qp)
        self.assertEqual(len(missings), 2)

    def test_missing_query_patterns_of_literals(self):
        qp = [cq.QueryPattern(cq.TARGET_LITERAL, "w", re.compile("w")), cq.QueryPattern(cq.TARGET_LITERAL, "x", re.compile("x"))]
        summary = []
        missings = cq.missing_query_patterns(summary, qp)
        self.assertEqual(len(missings), 2)
        self.assertEqual(missings[0].word, "w")
        self.assertEqual(missings[1].word, "x")
        
        summary = [("AClass", "void\tsomeMehtod")]
        missings = cq.missing_query_patterns(summary, qp)
        self.assertEqual(len(missings), 2)
        self.assertEqual(missings[0].word, "w")
        self.assertEqual(missings[1].word, "x")

        summary = ['"x"']
        missings = cq.missing_query_patterns(summary, qp)
        self.assertEqual(len(missings), 1)
        self.assertEqual(missings[0].word, "w")

        summary = ['"w"']
        missings = cq.missing_query_patterns(summary, qp)
        self.assertEqual(len(missings), 1)
        self.assertEqual(missings[0].word, "x")

        summary = ['"x"', '"w"']
        missings = cq.missing_query_patterns(summary, qp)
        self.assertEqual(len(missings), 0)
    
    def test_get_direct_sub_callnodes_of_body_node(self):
        subns = cq.get_direct_sub_callnodes_of_body_node(A_CALL_TREE.body)
        self.assertEqual(len(subns), 2)
        self.assertEqual(subns[0].invoked, new_invoked("C", "c"))
        self.assertEqual(subns[1].invoked, new_invoked("F", "f"))
        
        csubns = cq.get_direct_sub_callnodes_of_body_node(subns[0].body)
        self.assertEqual(csubns, [])

        fsubns = cq.get_direct_sub_callnodes_of_body_node(subns[1].body)
        self.assertEqual(len(fsubns), 1)
        self.assertEqual(fsubns[0].invoked, new_invoked("H", "h"))
    
    def test_get_lower_bound_call_nodes(self):
        cns = cq.get_lower_bound_call_nodes([A_CALL_TREE], A_PREDICATE)
        self.assertEqual(len(cns), 2)
        self.assertEqual(cns[0].invoked, new_invoked("C", "c"))
        self.assertEqual(cns[1].invoked, new_invoked("F", "f"))
    
    def test_treecut_with_callnode_depth(self):
        has_deeper_nodes = [False]
        tc0 = cq.treecut_with_callnode_depth(A_CALL_TREE, 0, has_deeper_nodes)
        expected = new_invoked("A", "a")
        self.assertEqual(tc0, expected)
        self.assertTrue(has_deeper_nodes[0])

        has_deeper_nodes = [False]
        tc1 = cq.treecut_with_callnode_depth(A_CALL_TREE, 1, has_deeper_nodes)
        expected = new_callnode("A", "a", 
            [ct.ORDERED_AND,
                new_invoked("B", "b"),
                new_invoked("C", "c"),
                new_invoked("F", "f"),
            ]
        )
        self.assertEqual(tc1, expected)
        self.assertTrue(has_deeper_nodes[0])

        has_deeper_nodes = [False]
        tc2 = cq.treecut_with_callnode_depth(A_CALL_TREE, 2, has_deeper_nodes)
        expected = new_callnode("A", "a", 
            [ct.ORDERED_AND,
                new_invoked("B", "b"),
                new_callnode("C", "c",
                    [ct.ORDERED_OR,
                        new_invoked("D", "d"),
                        new_invoked("E", "e"),
                    ]
                ),
                new_callnode("F", "f",
                    [ct.ORDERED_AND,
                        new_invoked("G", "g"),
                        new_invoked("H", "h")
                    ]
                )
            ]
        )
        self.assertEqual(tc2, expected)
        self.assertTrue(has_deeper_nodes[0])

        has_deeper_nodes = [False]
        tc3 = cq.treecut_with_callnode_depth(A_CALL_TREE, 3, has_deeper_nodes)
        self.assertEqual(tc3, A_CALL_TREE)
        self.assertFalse(has_deeper_nodes[0])
