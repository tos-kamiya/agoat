# coding: utf-8

import unittest

import re

import sys
import os.path
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))

import jimp_parser as jp
import calltree as ct
import calltree_summarizer as cs

def new_invoked(clz, msig, literals):
    return (jp.SPECIALINVOKE, clz, msig, literals, None)

def new_callnode(clz, msig, literals, recursive_cxt, body):
    return ct.CallNode((jp.SPECIALINVOKE, clz, msig, literals, None), recursive_cxt, body)

A_CALL_TREE = new_callnode("A", "a", ('"a"',), None,
    [ct.ORDERED_AND,
        new_invoked("B", "b", ('"b"',)),
        new_callnode("C", "c", ('"c"',), None,
            [ct.ORDERED_OR,
                new_invoked("D", "d", ('"d"',)),
                new_invoked("E", "e", ('"e"',)),
            ]
        ),
        new_callnode("F", "f", ('"f"',), None,
            [ct.ORDERED_AND,
                new_invoked("G", "g", ('"g"',)),
                new_callnode("H", "h", ('"h"',), None,
                    [ct.ORDERED_AND,
                    ]
                )
            ]
        )
    ]
)

RECURSIVE_CALL_TREE = new_callnode("A", "a", (), None,
    [ct.ORDERED_AND,
        new_callnode("R", "r", ('"r"',), ("R", "r"),
            [ct.ORDERED_AND,
                new_callnode("S", "s", ('"s"',), ("R", "r"),
                    new_invoked("R", "r", ('"r"',))
                )
            ]
        ),
        new_callnode("S", "s", ('"s1"',), ("S", "s"),
            [ct.ORDERED_AND,
                new_callnode("R", "r", ('"r"',), ("S", "s"),
                    new_invoked("S", "s", ('"s2"',))
                )
            ]
        )
    ]
)

S_BODY = [ct.ORDERED_AND,
    new_invoked("T", "t", ('"t"',))
]

SHARING_CALL_TREE = new_callnode("A", "a", ('"a"',), None,
    [ct.ORDERED_AND,
        new_callnode("B", "b", ('"b"',), None,
            new_callnode("S", "s", ('"s1"',), None, S_BODY)
        ),
        new_callnode("C", "c", ('"c"',), None,
            new_callnode("S", "s", ('"s2"',), None, S_BODY)
        )
    ]
)

class CalltreeSummarlizerTest(unittest.TestCase):
    def test_get_node_summary_empty(self):
        self.assertEqual(cs.get_node_summary_wo_memoization(None), [])

    def test_get_node_summary_table(self):
        summary_table = cs.extract_node_summary_table([A_CALL_TREE])
        asum = summary_table.get(("A", "a", None))
        self.assertSequenceEqual(asum, sorted(['"b"', '"c"', '"d"', '"e"', '"f"', '"g"', '"h"', 
            ('B', 'b'), ('C', 'c'), ('D', 'd'), ('E', 'e'), ('F', 'f'), ('G', 'g'), ('H', 'h')]))
        self.assertNotIn(("B", "b", None), summary_table)
        csum = summary_table.get(("C", "c", None))
        self.assertSequenceEqual(csum, sorted(['"d"', '"e"', ('D', 'd'), ('E', 'e')]))
        hsum = summary_table.get(("H", "h", None))
        self.assertSequenceEqual(hsum, [])

    def test_get_node_summary_table_recursive(self):
        summary_table = cs.extract_node_summary_table([RECURSIVE_CALL_TREE])
        rrsum = summary_table.get(("R", "r", ("R", "r")))
        self.assertSequenceEqual(rrsum, sorted(['"r"', '"s"', ('R', 'r'), ('S', 's')]))
        srsum = summary_table.get(("S", "s", ("R", "r")))
        self.assertSequenceEqual(srsum, sorted(['"r"', ('R', 'r') ]))
        rssum = summary_table.get(("R", "r", ("S", "s")))
        self.assertSequenceEqual(rssum, sorted(['"s2"', ('S', 's')]))
        sssum = summary_table.get(("S", "s", ("S", "s")))
        self.assertSequenceEqual(sssum, sorted(['"r"', '"s2"',('R', 'r'), ('S', 's')]))

    def test_get_node_summary_table_sharing(self):
        summary_table = cs.extract_node_summary_table([SHARING_CALL_TREE])
        expected = {
            ('A', 'a', None): sorted(['"b"', '"c"', '"s1"', '"s2"', '"t"', ('B', 'b'), ('C', 'c'), ('S', 's'), ('T', 't')]), 
            ('B', 'b', None): sorted(['"s1"', '"t"', ('S', 's'), ('T', 't')]), 
            ('S', 's', None): sorted(['"t"', ('T', 't')]), 
            ('C', 'c', None): sorted(['"s2"', '"t"', ('S', 's'), ('T', 't')])
        }
        self.assertEqual(summary_table, expected)


if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()