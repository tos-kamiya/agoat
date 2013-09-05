# coding: utf-8

import unittest

import os
import sys
import os.path
from cStringIO import StringIO
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))

import jimp_parser as jp


class JimpParserWSootOutputFilesTest(unittest.TestCase):

    def test_with_files(self):
        data_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), 'sootOutput')
        for root, dirs, files in os.walk(data_dir):
            for f in files:
                if f.endswith(".jimp"):
                    sys.stderr.write("> parsing %s\n" % f)
                    out = StringIO()
                    p = os.path.join(root, f)
                    jp.main(["jimp_parser", p], out=out)

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
