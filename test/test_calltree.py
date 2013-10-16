#coding: utf-8

import unittest

import pickle
import sys
import os.path
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))

import agoat.calltree as callee


class CalleeTest(unittest.TestCase):
    def test_callee_eq(self):
        c = callee.Invoked("cmd", "A\tvoid\tm", (), "A\t10")
        d = callee.Invoked("cmd", "A\tvoid\tm", (), "A\t10")
        e = callee.Invoked("cmd", "B\tvoid\tm", (), "B\t10")
        self.assertEqual(c, d)
        self.assertNotEqual(c, e)

    def test_callee_pickle(self):
        c = callee.Invoked("cmd", "A\tvoid\tm", (), "A\t10")
        b = pickle.dumps(c, protocol=1)
        c_cpy = pickle.loads(b)
        self.assertEqual(c, c_cpy)

    def test_callnode_eq(self):
        c = callee.Invoked("cmd", "A\tvoid\tm", (), "A\t10")
        d = callee.Invoked("cmd", "B\tvoid\tm", (), "B\t10")
        e = callee.Invoked("cmd", "C\tvoid\tm", (), "C\t10")
        n = callee.CallNode(c, None, d)
        m = callee.CallNode(c, None, d)
        self.assertEqual(n, m)
        m = callee.CallNode(c, None, e)
        self.assertNotEqual(n, m)
        m = callee.CallNode(d, None, c)
        self.assertNotEqual(n, m)
        m = callee.CallNode(c, 1, d)
        self.assertNotEqual(n, m)

    def test_callnode_pickle(self):
        c = callee.Invoked("cmd", "A\tvoid\tm", (), "A\t10")
        d = callee.Invoked("cmd", "B\tvoid\tm", (), "B\t10")
        n = callee.CallNode(c, None, d)
        b = pickle.dumps(n, protocol=1)
        n_cpy = pickle.loads(b)
        self.assertEqual(n, n_cpy)


if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()