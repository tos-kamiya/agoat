# coding: utf-8

import unittest

import re

import sys
import os.path
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))

import jimp_parser as jp
import calltree as ct
import calltree_query as cq
import summary

def new_invoked(clz, msig):
    return (jp.SPECIALINVOKE, clz, msig, (), None)

def new_callnode(clz, msig, body):
    return ct.CallNode((jp.SPECIALINVOKE, clz, msig, (), None), None, body)

def new_callnode_w_rc(clz, msig, rc, body):
    return ct.CallNode((jp.SPECIALINVOKE, clz, msig, (), None), rc, body)

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


A_CALL_TREE_W_DEPTH = new_callnode_w_rc("A", "a", 3,
    [ct.ORDERED_AND,
        new_invoked("B", "b"),
        new_callnode_w_rc("C", "c", 2,
            [ct.ORDERED_OR,
                new_invoked("D", "d"),
                new_invoked("E", "e"),
            ]
        ),
        new_callnode_w_rc("F", "f", 2,
            [ct.ORDERED_AND,
                new_invoked("G", "g"),
                new_callnode_w_rc("H", "h", 1,
                    [ct.ORDERED_AND,
                    ]
                )
            ]
        )
    ]
)


def A_PREDICATE(call_node):
    return call_node.invoked[1] in ('A', 'B', 'C', 'F')


class QueryTest(unittest.TestCase):
    def test_unmatched_patterns_to_methods(self):
        qp = [cq.MethodQueryPattern("w"), cq.MethodQueryPattern("x")]
        query = cq.Query(qp)
        sumry = summary.Summary()
        missings = query.unmatched_patterns(sumry)
        self.assertEqual(len(missings), 2)
        self.assertEqual(missings[0].word, "w")
        self.assertEqual(missings[1].word, "x")

        sumry = summary.Summary(["AClass\tvoid\tsomeMehtod"])
        missings = query.unmatched_patterns(sumry)
        self.assertEqual(len(missings), 2)
        self.assertEqual(missings[0].word, "w")
        self.assertEqual(missings[1].word, "x")

        sumry = summary.Summary(["A\tvoid\tw"])
        missings = query.unmatched_patterns(sumry)
        self.assertEqual(len(missings), 1)
        self.assertEqual(missings[0].word, "x")

        sumry = summary.Summary(["B\tint\tx"])
        missings = query.unmatched_patterns(sumry)
        self.assertEqual(len(missings), 1)
        self.assertEqual(missings[0].word, "w")

        sumry = summary.Summary(["A\tvoid\tw", "B\tint\tx"])
        missings = query.unmatched_patterns(sumry)
        self.assertEqual(len(missings), 0)

        sumry = summary.Summary(literals=['"w x someliteral string"'])
        missings = query.unmatched_patterns(sumry)
        self.assertEqual(len(missings), 2)

    def test_unmatched_patterns_to_literals(self):
        qp = [cq.LiteralQueryPattern("w"), cq.LiteralQueryPattern("x")]
        query = cq.Query(qp)
        sumry = summary.Summary()
        missings = query.unmatched_patterns(sumry)
        self.assertEqual(len(missings), 2)
        self.assertEqual(missings[0].word, "w")
        self.assertEqual(missings[1].word, "x")
        self.assertFalse(query.is_partially_filled_by(sumry))
        self.assertFalse(query.is_fullfilled_by(sumry))

        sumry = summary.Summary(["AClass\tvoid\tsomeMehtod"])
        missings = query.unmatched_patterns(sumry)
        self.assertEqual(len(missings), 2)
        self.assertEqual(missings[0].word, "w")
        self.assertEqual(missings[1].word, "x")
        self.assertFalse(query.is_partially_filled_by(sumry))
        self.assertFalse(query.is_fullfilled_by(sumry))

        sumry = summary.Summary(literals=['"x"'])
        missings = query.unmatched_patterns(sumry)
        self.assertEqual(len(missings), 1)
        self.assertEqual(missings[0].word, "w")
        self.assertTrue(query.is_partially_filled_by(sumry))
        self.assertFalse(query.is_fullfilled_by(sumry))

        sumry = summary.Summary(literals=['"w"'])
        missings = query.unmatched_patterns(sumry)
        self.assertEqual(len(missings), 1)
        self.assertEqual(missings[0].word, "x")
        self.assertTrue(query.is_partially_filled_by(sumry))
        self.assertFalse(query.is_fullfilled_by(sumry))

        sumry = summary.Summary(literals=['"x"', '"w"'])
        missings = query.unmatched_patterns(sumry)
        self.assertEqual(len(missings), 0)
        self.assertTrue(query.is_partially_filled_by(sumry))
        self.assertTrue(query.is_fullfilled_by(sumry))
    
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
        expected = new_callnode_w_rc("A", "a", 1,
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
        expected = new_callnode_w_rc("A", "a", 2,
            [ct.ORDERED_AND,
                new_invoked("B", "b"),
                new_callnode_w_rc("C", "c", 1,
                    [ct.ORDERED_OR,
                        new_invoked("D", "d"),
                        new_invoked("E", "e"),
                    ]
                ),
                new_callnode_w_rc("F", "f", 1,
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
        self.assertEqual(tc3, A_CALL_TREE_W_DEPTH)
        self.assertFalse(has_deeper_nodes[0])


class QueryPatternTest(unittest.TestCase):
    def test_compile(self):
        pat = cq.compile_query("w")
        self.assertTrue(isinstance(pat, cq.AnyQueryPattern))

        pat = cq.compile_query("m.w")
        self.assertTrue(isinstance(pat, cq.MethodQueryPattern))

        pat = cq.compile_query("t.w")
        self.assertTrue(isinstance(pat, cq.TypeQueryPattern))

        pat = cq.compile_query('"w')
        self.assertTrue(isinstance(pat, cq.LiteralQueryPattern))
