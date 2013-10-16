#coding: utf-8

import unittest

import sys
import os.path
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))

import agoat.jimp_parser as jp
import agoat._calltree_data_formatter as cdf


class CalleeDataFormatterTest(unittest.TestCase):
    def test_omit_trivial_package(self):
        try:
            old_op = cdf.OMITTED_PACKAGES
            cdf.OMITTED_PACKAGES = ["java.lang."]
            self.assertEqual(cdf.omit_trivial_package("java.util.HashMap"), "java.util.HashMap")
            self.assertEqual(cdf.omit_trivial_package("java.lang.String"), "String")
        finally:
            cdf.OMITTED_PACKAGES = old_op

    def test_format_clzmsig(self):
        clzmsig = jp.ClzMethodSig("C", None, "m", ("int", "double"))
        self.assertEqual(cdf.format_clzmsig(clzmsig), "C void m(int,double)")
        clzmsig = jp.ClzMethodSig("C", "void", "m", ())
        self.assertEqual(cdf.format_clzmsig(clzmsig), "C void m()")


if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()