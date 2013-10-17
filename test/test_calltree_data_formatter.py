#coding: utf-8

import unittest

import sys
import os.path
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))

import agoat.jimp_parser as jp
import agoat._calltree_data_formatter as cdf
import agoat.calltree as ct

def cm(clz, method):
    return jp.ClzMethodSig(clz, 'void', method, ())

def new_invoked(clzmsig, literals):
    return ct.Invoked(jp.SPECIALINVOKE, clzmsig, literals, None)

def new_callnode(clzmsig, literals, recursive_cxt, body):
    return ct.CallNode(new_invoked(clzmsig, literals), recursive_cxt, body)

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


class CalleeDataFormatterTest(unittest.TestCase):
    def test_replace_callnode_body_with_label(self):
        act_n, act_tbl = cdf.replace_callnode_body_with_label(A_CALL_TREE)
        ia = new_invoked(cm('A', 'a'), ('"a"',))
        na = (cm('A', 'a'), None)
        ib = new_invoked(cm('B', 'b'), ('"b"',))
        ic = new_invoked(cm('C', 'c'), ('"c"',))
        nc = (cm('C', 'c'), None)
        id_ = new_invoked(cm('D', 'd'), ('"d"',))
        ie = new_invoked(cm('E', 'e'), ('"e"',))
        if_ = new_invoked(cm('F', 'f'), ('"f"',))
        nf = (cm('F', 'f'), None)
        ig = new_invoked(cm('G', 'g'), ('"g"',))
        ih = new_invoked(cm('H', 'h'), ('"h"',))
        nh = (cm('H', 'h'), None)
        self.assertEqual(act_n, ct.CallNode(ia, None, cdf.Node(na)))
        self.assertSequenceEqual(act_tbl[nf][1], [ct.ORDERED_AND, ig, ct.CallNode(ih, None, cdf.Node(nh))])
        self.assertSequenceEqual(act_tbl[na][1], [ct.ORDERED_AND, ib, ct.CallNode(ic, None, cdf.Node(nc)), ct.CallNode(if_, None, cdf.Node(nf))])
        self.assertSequenceEqual(act_tbl[nc][1], [ct.ORDERED_OR, id_, ie])
        self.assertSequenceEqual(act_tbl[nh][1], [ct.ORDERED_AND])


if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()