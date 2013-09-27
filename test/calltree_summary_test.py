# coding: utf-8

import unittest

import sys
import os.path
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))

import jimp_parser as jp
import calltree as ct
import calltree_summary as cs

def cm(clz, method):
    return jp.ClzMethodSig(clz, 'void', method, ())

def new_invoked(clzmsig, literals):
    return ct.Invoked(jp.SPECIALINVOKE, clzmsig, literals, None)

def new_callnode(clzmsig, literals, recursive_cxt, body):
    return ct.CallNode(ct.Invoked(jp.SPECIALINVOKE, clzmsig, literals, None), recursive_cxt, body)

A_CALL_TREE = new_callnode(cm('A', 'a'), ('"a"',), None,
    [ct.ORDERED_AND,
        new_invoked(cm('B', 'b'), ('"b"',)),
        new_callnode(cm('C', 'c'), ('"c"',), None,
            [ct.ORDERED_OR,
                new_invoked(cm('D', 'd'), ('"d"',)),
                new_invoked(cm('E', 'e'), ('"e"',)),
            ]
        ),
        new_callnode(cm('F', 'f'), ('"f"',), None,
            [ct.ORDERED_AND,
                new_invoked(cm('G', 'g'), ('"g"',)),
                new_callnode(cm('H', 'h'), ('"h"',), None,
                    [ct.ORDERED_AND,
                    ]
                )
            ]
        )
    ]
)

RECURSIVE_CALL_TREE = new_callnode(cm('A', 'a'), (), None,
    [ct.ORDERED_AND,
        new_callnode(cm('R', 'r'), ('"r"',), (cm('R', 'r')),
            [ct.ORDERED_AND,
                new_callnode(cm('S', 's'), ('"s"',), (cm('R', 'r')),
                    new_invoked(cm('R', 'r'), ('"r"',))
                )
            ]
        ),
        new_callnode(cm('S', 's'), ('"s1"',), (cm('S', 's')),
            [ct.ORDERED_AND,
                new_callnode(cm('R', 'r'), ('"r"',), (cm('S', 's')),
                    new_invoked(cm('S', 's'), ('"s2"',))
                )
            ]
        )
    ]
)

S_BODY = [ct.ORDERED_AND,
    new_invoked(cm('T', 't'), ('"t"',))
]

SHARING_CALL_TREE = new_callnode(cm('A', 'a'), ('"a"',), None,
    [ct.ORDERED_AND,
        new_callnode(cm('B', 'b'), ('"b"',), None,
            new_callnode(cm('S', 's'), ('"s1"',), None, S_BODY)
        ),
        new_callnode(cm('C', 'c'), ('"c"',), None,
            new_callnode(cm('S', 's'), ('"s2"',), None, S_BODY)
        )
    ]
)

class CalltreeSummarlizerTest(unittest.TestCase):
    def test_get_node_summary_empty(self):
        self.assertEqual(cs.get_node_summary_wo_memoization(None), cs.Summary())

    def test_get_node_summary_table(self):
        summary_table = cs.extract_node_summary_table([A_CALL_TREE])
        asum = summary_table.get((cm('A', 'a'), None))
        aexpected = cs.Summary([cm('B', 'b'), cm('C', 'c'), cm('D', 'd'), cm('E', 'e'), cm('F', 'f'), cm('G', 'g'), cm('H', 'h')],
                ['"b"', '"c"', '"d"', '"e"', '"f"', '"g"', '"h"'])
        self.assertEqual(asum, aexpected)
        self.assertNotIn((cm("B", "b"), None), summary_table)
        csum = summary_table.get((cm("C", "c"), None))
        cexpected = cs.Summary([cm('D', 'd'), cm('E', 'e')], ['"d"', '"e"'])
        self.assertEqual(csum, cexpected)
        hsum = summary_table.get((cm("H", "h"), None))
        self.assertEqual(hsum, cs.Summary())

    def test_get_node_summary_table_recursive(self):
        summary_table = cs.extract_node_summary_table([RECURSIVE_CALL_TREE])
        rrsum = summary_table.get((cm('R', 'r'), (cm('R', 'r'))))
        self.assertEqual(rrsum, cs.Summary([cm('R', 'r'), cm('S', 's')], ['"r"', '"s"']))

        srsum = summary_table.get((cm('S', 's'), (cm('R', 'r'))))
        self.assertEqual(srsum, cs.Summary([cm('R', 'r')], ['"r"']))

        rssum = summary_table.get((cm('R', 'r'), (cm('S', 's'))))
        self.assertEqual(rssum, cs.Summary([cm('S', 's')], ['"s2"']))

        sssum = summary_table.get((cm('S', 's'), (cm('S', 's'))))
        self.assertEqual(sssum, cs.Summary([cm('R', 'r'), cm('S', 's')], ['"r"', '"s2"']))

    def test_get_node_summary_table_sharing(self):
        summary_table = cs.extract_node_summary_table([SHARING_CALL_TREE])
        expected = {
            (cm('A', 'a'), None): cs.Summary([cm('B', 'b'), cm('C', 'c'), cm('S', 's'), cm('T', 't')],
                    ['"b"', '"c"', '"s1"', '"s2"', '"t"']),
            (cm('B', 'b'), None): cs.Summary([cm('S', 's'), cm('T', 't')], ['"s1"', '"t"']), 
            (cm('S', 's'), None): cs.Summary([cm('T', 't')], ['"t"']), 
            (cm('C', 'c'), None): cs.Summary([cm('S', 's'), cm('T', 't')], ['"s2"', '"t"'])
        }
        self.assertEqual(summary_table, expected)


if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()