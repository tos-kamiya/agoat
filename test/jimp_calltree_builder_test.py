#coding: utf-8

import unittest

import sys
import os.path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))

import jimp_parser as jp
import jimp_calltree_builder as jcb

class ClassDataStubOnlyBase(object):
    def __init__(self, base_name):
        self.base_name = base_name

class ClassDataStubOnlyMethods(object):
    def __init__(self, methods):
        self.methods = methods

class MethodDataStubOnlyCode(object):
    def __init__(self, code):
        self.code = code

class JimpCalltreeBuilderTest(unittest.TestCase):
    def test_extract_class_hierachy_empty(self):
        class_table = {}
        class_to_descendants = jcb.extract_class_hierarchy(class_table, include_indirect_decendants=True)
        self.assertEqual(class_to_descendants, {})
    
    def test_extract_class_hierachy_simple(self):
        class_table = { 'B': ClassDataStubOnlyBase('A'), 'C': ClassDataStubOnlyBase('A') }
        class_to_descendants = jcb.extract_class_hierarchy(class_table, include_indirect_decendants=True)
        self.assertEqual(class_to_descendants, { 'A': set(['B', 'C'])})

    def test_extract_class_hierachy_2hop(self):
        class_table = { 'B': ClassDataStubOnlyBase('A'), 'C': ClassDataStubOnlyBase('B') }
        class_to_descendants = jcb.extract_class_hierarchy(class_table, include_indirect_decendants=True)
        self.assertEqual(class_to_descendants, { 'A': set(['B', 'C']), 'B': set(['C'])})

    def test_resolve_dispatch_noinheritance(self):
        class_to_methods = { 'A': ['a', 'b'], 'M': ['m', 'n'], 'P': ['p', 'q'] }
        class_to_descendants = {}
        recv_method_to_defs = jcb.resolve_dispatch(class_to_methods, class_to_descendants)
        self.assertEqual(recv_method_to_defs, {
            ('A', 'a'): ['A'], ('A', 'b'): ['A'], 
            ('M', 'm'): ['M'], ('M', 'n'): ['M'], 
            ('P', 'p'): ['P'], ('P', 'q'): ['P']
        })

    def test_resolve_dispatch_nooverride(self):
        class_to_methods = { 'A': ['a', 'b'], 'M': ['m', 'n'], 'P': ['p', 'q'] }
        class_to_descendants = { 'A': set(['M', 'P']) }
        recv_method_to_defs = jcb.resolve_dispatch(class_to_methods, class_to_descendants)
        self.assertEqual(recv_method_to_defs, {
            ('A', 'a'): ['A'], ('A', 'b'): ['A'], 
            ('M', 'm'): ['M'], ('M', 'n'): ['M'], 
            ('P', 'p'): ['P'], ('P', 'q'): ['P']
        })

    def test_resolve_dispatch_inheritance_override(self):
        class_to_methods = { 'A': ['a', 'b'], 'M': ['b', 'n'], 'P': ['b', 'q'] }
        class_to_descendants = { 'A': set(['M', 'P']) }
        recv_method_to_defs = jcb.resolve_dispatch(class_to_methods, class_to_descendants)
        self.assertEqual(recv_method_to_defs, {
            ('A', 'a'): ['A'], ('A', 'b'): ['A', 'M', 'P'], 
            ('M', 'b'): ['M'], ('M', 'n'): ['M'], 
            ('P', 'b'): ['P'], ('P', 'q'): ['P']
        })

        class_to_descendants = { 'A': set(['M', 'P']), 'M': set(['P']) }
        recv_method_to_defs = jcb.resolve_dispatch(class_to_methods, class_to_descendants)
        self.assertEqual(recv_method_to_defs, {
            ('A', 'a'): ['A'], ('A', 'b'): ['A', 'M', 'P'], 
            ('M', 'b'): ['M', 'P'], ('M', 'n'): ['M'], 
            ('P', 'b'): ['P'], ('P', 'q'): ['P']
        })

    def test_find_methods_involved_in_recursive_call_chain_direct(self):
        class_table = {
            'A': ClassDataStubOnlyMethods({ 
                'main': MethodDataStubOnlyCode([
                    (jp.INVOKE, 'B', 'b')
                ])
            }),
            'B': ClassDataStubOnlyMethods({ 
                'b': MethodDataStubOnlyCode([
                    (jp.INVOKE, 'B', 'b')
                ])
            }),
        }
        recv_method_to_defs = {
            ('A', 'main'): ['A'],
            ('B', 'b'): ['B'],
        }
        entry_point = ('A', 'main')
        methods_ircc = jcb.find_methods_involved_in_recursive_call_chain(class_table, recv_method_to_defs, entry_point, 
                include_direct_recursive_calls=True)
        self.assertEqual(methods_ircc, [('B', 'b')])
        methods_ircc = jcb.find_methods_involved_in_recursive_call_chain(class_table, recv_method_to_defs, entry_point, 
                include_direct_recursive_calls=False)
        self.assertEqual(methods_ircc, [])

    def test_find_methods_involved_in_recursive_call_chain_indirect(self):
        class_table = {
            'A': ClassDataStubOnlyMethods({ 
                'main': MethodDataStubOnlyCode([
                    (jp.INVOKE, 'B', 'b')
                ])
            }),
            'B': ClassDataStubOnlyMethods({ 
                'b': MethodDataStubOnlyCode([
                    (jp.INVOKE, 'C', 'c')
                ])
            }),
            'C': ClassDataStubOnlyMethods({ 
                'c': MethodDataStubOnlyCode([
                    (jp.INVOKE, 'B', 'b')
                ])
            }),
        }
        recv_method_to_defs = {
            ('A', 'main'): ['A'],
            ('B', 'b'): ['B'],
            ('C', 'c'): ['C'],
        }
        entry_point = ('A', 'main')
        methods_ircc = jcb.find_methods_involved_in_recursive_call_chain(class_table, recv_method_to_defs, entry_point, 
                include_direct_recursive_calls=True)
        self.assertEqual(methods_ircc, [('B', 'b'), ('C', 'c')])
        methods_ircc = jcb.find_methods_involved_in_recursive_call_chain(class_table, recv_method_to_defs, entry_point, 
                include_direct_recursive_calls=False)
        self.assertEqual(methods_ircc, [('B', 'b'), ('C', 'c')])
    
if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()