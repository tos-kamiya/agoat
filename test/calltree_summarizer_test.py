# coding: utf-8

import unittest

import sys
import os.path
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))

import summary
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
        self.assertEqual(cs.get_node_summary_wo_memoization(None), summary.Summary())

    def test_get_node_summary_table(self):
        summary_table = cs.extract_node_summary_table([A_CALL_TREE])
        asum = summary_table.get(("A", "a", None))
        aexpected = summary.Summary(['B\tb', 'C\tc', 'D\td', 'E\te', 'F\tf', 'G\tg', 'H\th'],
                ['"b"', '"c"', '"d"', '"e"', '"f"', '"g"', '"h"'])
        self.assertEqual(asum, aexpected)
        self.assertNotIn(("B", "b", None), summary_table)
        csum = summary_table.get(("C", "c", None))
        cexpected = summary.Summary(['D\td', 'E\te'], ['"d"', '"e"'])
        self.assertEqual(csum, cexpected)
        hsum = summary_table.get(("H", "h", None))
        self.assertEqual(hsum, summary.Summary())

    def test_get_node_summary_table_recursive(self):
        summary_table = cs.extract_node_summary_table([RECURSIVE_CALL_TREE])
        rrsum = summary_table.get(("R", "r", ("R", "r")))
        self.assertEqual(rrsum, summary.Summary(['R\tr', 'S\ts'], ['"r"', '"s"']))

        srsum = summary_table.get(("S", "s", ("R", "r")))
        self.assertEqual(srsum, summary.Summary(['R\tr'], ['"r"']))

        rssum = summary_table.get(("R", "r", ("S", "s")))
        self.assertEqual(rssum, summary.Summary(['S\ts'], ['"s2"']))

        sssum = summary_table.get(("S", "s", ("S", "s")))
        self.assertEqual(sssum, summary.Summary(['R\tr', 'S\ts'], ['"r"', '"s2"']))

    def test_get_node_summary_table_sharing(self):
        summary_table = cs.extract_node_summary_table([SHARING_CALL_TREE])
        expected = {
            ('A', 'a', None): summary.Summary(['B\tb', 'C\tc', 'S\ts', 'T\tt'],
                    ['"b"', '"c"', '"s1"', '"s2"', '"t"']),
            ('B', 'b', None): summary.Summary(['S\ts', 'T\tt'], ['"s1"', '"t"']), 
            ('S', 's', None): summary.Summary(['T\tt'], ['"t"']), 
            ('C', 'c', None): summary.Summary(['S\ts', 'T\tt'], ['"s2"', '"t"'])
        }
        self.assertEqual(summary_table, expected)


if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()