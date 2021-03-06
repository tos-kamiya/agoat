# coding: utf-8

import unittest

import re

import sys
import os.path
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))

from agoat._utilities import quote

import agoat.jimp_parser as jp
import agoat.calltree as ct
import agoat.calltree_query as cq

def new_invoked(clz, msig):
    return ct.Invoked(jp.SPECIALINVOKE, clz + '\t' + msig, (), None)

def new_callnode(clz, msig, body):
    return ct.CallNode(ct.Invoked(jp.SPECIALINVOKE, clz + '\t' + msig, (), None), None, body)

def new_callnode_w_rc(clz, msig, rc, body):
    return ct.CallNode(ct.Invoked(jp.SPECIALINVOKE, clz + '\t' + msig, (), None), rc, body)

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
    return call_node.invoked.callee.split('\t')[0] in ('A', 'B', 'C', 'F')


class QueryTest(unittest.TestCase):
    def test_unmatched_patterns_to_methods(self):
        qp = [cq.MethodQueryPattern("w"), cq.MethodQueryPattern("x")]
        query = cq.Query(qp)
        sumry = cq.Summary()
        missings = query.unmatched_patterns(sumry)
        self.assertEqual(len(missings), 2)
        self.assertEqual(missings[0].word, "w")
        self.assertEqual(missings[1].word, "x")

        sumry = cq.Summary(["AClass\tvoid\tsomeMehtod"])
        missings = query.unmatched_patterns(sumry)
        self.assertEqual(len(missings), 2)
        self.assertEqual(missings[0].word, "w")
        self.assertEqual(missings[1].word, "x")

        sumry = cq.Summary(["A\tvoid\tw"])
        missings = query.unmatched_patterns(sumry)
        self.assertEqual(len(missings), 1)
        self.assertEqual(missings[0].word, "x")

        sumry = cq.Summary(["B\tint\tx"])
        missings = query.unmatched_patterns(sumry)
        self.assertEqual(len(missings), 1)
        self.assertEqual(missings[0].word, "w")

        sumry = cq.Summary(["A\tvoid\tw", "B\tint\tx"])
        missings = query.unmatched_patterns(sumry)
        self.assertEqual(len(missings), 0)

        sumry = cq.Summary(literals=['"w x someliteral string"'])
        missings = query.unmatched_patterns(sumry)
        self.assertEqual(len(missings), 2)

    def test_unmatched_patterns_to_literals(self):
        qp = [cq.LiteralQueryPattern("w"), cq.LiteralQueryPattern("x")]
        query = cq.Query(qp)
        sumry = cq.Summary()
        missings = query.unmatched_patterns(sumry)
        self.assertEqual(len(missings), 2)
        self.assertEqual(missings[0].word, "w")
        self.assertEqual(missings[1].word, "x")
        self.assertFalse(query.is_partially_filled_by(sumry))
        self.assertFalse(query.is_fulfilled_by(sumry))

        sumry = cq.Summary(["AClass\tvoid\tsomeMehtod"])
        missings = query.unmatched_patterns(sumry)
        self.assertEqual(len(missings), 2)
        self.assertEqual(missings[0].word, "w")
        self.assertEqual(missings[1].word, "x")
        self.assertFalse(query.is_partially_filled_by(sumry))
        self.assertFalse(query.is_fulfilled_by(sumry))

        sumry = cq.Summary(literals=['"x"'])
        missings = query.unmatched_patterns(sumry)
        self.assertEqual(len(missings), 1)
        self.assertEqual(missings[0].word, "w")
        self.assertTrue(query.is_partially_filled_by(sumry))
        self.assertFalse(query.is_fulfilled_by(sumry))

        sumry = cq.Summary(literals=['"w"'])
        missings = query.unmatched_patterns(sumry)
        self.assertEqual(len(missings), 1)
        self.assertEqual(missings[0].word, "x")
        self.assertTrue(query.is_partially_filled_by(sumry))
        self.assertFalse(query.is_fulfilled_by(sumry))

        sumry = cq.Summary(literals=['"x"', '"w"'])
        missings = query.unmatched_patterns(sumry)
        self.assertEqual(len(missings), 0)
        self.assertTrue(query.is_partially_filled_by(sumry))
        self.assertTrue(query.is_fulfilled_by(sumry))

    def test_quoted_and_unquoted(self):
        word_japanese_a = u"あ"
        l = quote(word_japanese_a)
        m = quote(word_japanese_a)
        t = quote(word_japanese_a)
        utf8_word_japanese_a = word_japanese_a.encode("utf-8")

        qpl = cq.LiteralQueryPattern(utf8_word_japanese_a)
        self.assertTrue(qpl.matches_literal(l))
        self.assertFalse(qpl.matches_method(m))
        self.assertFalse(qpl.matches_type(t))

        qpm = cq.MethodQueryPattern(utf8_word_japanese_a)
        self.assertFalse(qpm.matches_literal(l))
        self.assertTrue(qpm.matches_method(m))
        self.assertFalse(qpm.matches_type(t))

        qpt = cq.TypeQueryPattern(utf8_word_japanese_a)
        self.assertFalse(qpt.matches_literal(l))
        self.assertFalse(qpt.matches_method(m))
        self.assertTrue(qpt.matches_type(t))

        qpa = cq.AnyQueryPattern(utf8_word_japanese_a)
        self.assertTrue(qpa.matches_literal(l))
        self.assertTrue(qpa.matches_method(m))
        self.assertTrue(qpa.matches_type(t))

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


if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
