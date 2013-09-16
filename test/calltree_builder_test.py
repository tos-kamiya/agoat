# coding: utf-8

import unittest

import sys
import os.path
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))

import andor_tree as at
import jimp_parser as jp
import calltree_builder as cb


class ClassDataStubOnlyBase(object):

    def __init__(self, base_name):
        self.base_name = base_name
        self.interf_names = None


class ClassDataStubOnlyMethods(object):

    def __init__(self, class_name, methods):
        self.class_name = class_name
        self.methods = methods


class MethodDataStubOnlyCode(object):

    def __init__(self, method_sig, code):
        self.method_sig = method_sig
        self.code = code


def rv(m):
    return 'void\t' + m

def mnamc(m):
    return (m, 0)

class CalltreeBuilderTest(unittest.TestCase):

    def test_extract_class_hierachy_empty(self):
        class_table = {}
        class_to_descendants = cb.extract_class_hierarchy(class_table, include_indirect_decendants=True)
        self.assertEqual(class_to_descendants, {})

    def test_extract_class_hierachy_simple(self):
        class_table = {
            'B': ClassDataStubOnlyBase('A'), 
            'C': ClassDataStubOnlyBase('A')
        }
        class_to_descendants = cb.extract_class_hierarchy(class_table, include_indirect_decendants=True)
        self.assertEqual(class_to_descendants, {'A': {'B': 1, 'C': 1}})

    def test_extract_class_hierachy_2hop(self):
        class_table = {
            'B': ClassDataStubOnlyBase('A'), 
            'C': ClassDataStubOnlyBase('B')
        }
        class_to_descendants = cb.extract_class_hierarchy(class_table, include_indirect_decendants=True)
        self.assertEqual(class_to_descendants, {
             'A': {'B': 1, 'C':2}, 
             'B': {'C': 1}
        })

    def test_resolve_dispatch_noinheritance(self):
        class_to_methods = {'A': [rv('a'), rv('b')], 'M': [rv('m'), rv('n')], 'P': [rv('p'), rv('q')]}
        class_to_descendants = {}
        recv_method_to_defs = cb.make_dispatch_table(class_to_methods, class_to_descendants)
        self.assertEqual(recv_method_to_defs, {
            ('A', mnamc('a')): [('A', rv('a'))],
            ('A', mnamc('b')): [('A', rv('b'))],
            ('M', mnamc('m')): [('M', rv('m'))],
            ('M', mnamc('n')): [('M', rv('n'))],
            ('P', mnamc('p')): [('P', rv('p'))],
            ('P', mnamc('q')): [('P', rv('q'))]
        })

    def test_resolve_dispatch_nooverride(self):
        class_to_methods = {'A': [rv('a'), rv('b')], 'M': [rv('m'), rv('n')], 'P': [rv('p'), rv('q')]}
        class_to_descendants = {'A': {'M': 1, 'P': 1}}
        recv_method_to_defs = cb.make_dispatch_table(class_to_methods, class_to_descendants)
        self.assertEqual(recv_method_to_defs, {
            ('A', mnamc('a')): [('A', rv('a'))],
            ('A', mnamc('b')): [('A', rv('b'))],
            ('M', mnamc('a')): [('A', rv('a'))],
            ('M', mnamc('b')): [('A', rv('b'))],
            ('M', mnamc('m')): [('M', rv('m'))],
            ('M', mnamc('n')): [('M', rv('n'))],
            ('P', mnamc('a')): [('A', rv('a'))],
            ('P', mnamc('b')): [('A', rv('b'))],
            ('P', mnamc('p')): [('P', rv('p'))],
            ('P', mnamc('q')): [('P', rv('q'))]
        })

    def test_resolve_dispatch_inheritance_override(self):
        class_to_methods = {'A': [rv('a'), rv('b')], 'M': [rv('b'), rv('m')], 'P': [rv('b'), rv('p')]}
        class_to_descendants = {'A': {'M': 1, 'P': 1}}
        recv_method_to_defs = cb.make_dispatch_table(class_to_methods, class_to_descendants)
        self.assertEqual(recv_method_to_defs, {
            ('A', mnamc('a')): [('A', rv('a'))],
            ('A', mnamc('b')): [('A', rv('b')), ('M', rv('b')), ('P', rv('b'))],
            ('M', mnamc('a')): [('A', rv('a'))],
            ('M', mnamc('b')): [('M', rv('b'))],
            ('M', mnamc('m')): [('M', rv('m'))],
            ('P', mnamc('a')): [('A', rv('a'))],
            ('P', mnamc('b')): [('P', rv('b'))],
            ('P', mnamc('p')): [('P', rv('p'))]}
        )

        class_to_descendants = {'A': {'M':1, 'P': 2}, 'M': {'P': 1}}
        recv_method_to_defs = cb.make_dispatch_table(class_to_methods, class_to_descendants)
        self.assertEqual(recv_method_to_defs, {
            ('A', mnamc('a')): [('A', rv('a'))], 
            ('A', mnamc('b')): [('A', rv('b')), ('M', rv('b')), ('P', rv('b'))],
            ('M', mnamc('a')): [('A', rv('a'))], 
            ('M', mnamc('b')): [('M', rv('b')), ('P', rv('b'))], 
            ('M', mnamc('m')): [('M', rv('m'))],
            ('P', mnamc('a')): [('A', rv('a'))], 
            ('P', mnamc('m')): [('M', rv('m'))],
            ('P', mnamc('b')): [('P', rv('b'))], 
            ('P', mnamc('p')): [('P', rv('p'))]
        })

    def test_find_methods_involved_in_recursive_call_chain_direct(self):
        class_table = {
            'A': ClassDataStubOnlyMethods('A', {
                rv('main'): MethodDataStubOnlyCode(rv('main'), [at.ORDERED_AND,
                    (jp.INVOKE, 'B', rv('b'))
                ])
            }),
            'B': ClassDataStubOnlyMethods('B', {
                rv('b'): MethodDataStubOnlyCode(rv('b'), [at.ORDERED_AND,
                    (jp.INVOKE, 'B', rv('b'))
                ])
            }),
        }
        class_to_descendants = {}
        recv_method_to_defs = {
            ('A', mnamc('main')): [('A', rv('main'))],
            ('B', mnamc('b')): [('B', rv('b'))],
        }
        resolve_dispatch = cb.gen_method_dispatch_resolver(class_table, class_to_descendants, recv_method_to_defs)
        entry_point = ('A', rv('main'))
        methods_ircc = cb.find_methods_involved_in_recursive_call_chain(
            entry_point, resolve_dispatch,
            include_direct_recursive_calls=True)
        self.assertEqual(methods_ircc, [('B', rv('b'))])
        methods_ircc = cb.find_methods_involved_in_recursive_call_chain(
            entry_point, resolve_dispatch,
            include_direct_recursive_calls=False)
        self.assertEqual(methods_ircc, [])
 
    def test_find_methods_involved_in_recursive_call_chain_indirect(self):
        class_table = {
            'A': ClassDataStubOnlyMethods('A', {
                rv('main'): MethodDataStubOnlyCode(rv('main'), [at.ORDERED_AND,
                    (jp.INVOKE, 'B', rv('b'))
                ])
            }),
            'B': ClassDataStubOnlyMethods('B', {
                rv('b'): MethodDataStubOnlyCode(rv('b'), [at.ORDERED_AND,
                    (jp.INVOKE, 'C', rv('c'))
                ])
            }),
            'C': ClassDataStubOnlyMethods('C', {
                rv('c'): MethodDataStubOnlyCode(rv('c'), [at.ORDERED_AND,
                    (jp.INVOKE, 'B', rv('b'))
                ])
            }),
        }
        recv_method_to_defs = {
            ('A', mnamc('main')): [('A', rv('main'))],
            ('B', mnamc('b')): [('B', rv('b'))],
            ('C', mnamc('c')): [('C', rv('c'))],
        }
        class_to_descendants = {}
        resolve_dispatch = cb.gen_method_dispatch_resolver(class_table, class_to_descendants, recv_method_to_defs)
        entry_point = ('A', rv('main'))
        methods_ircc = cb.find_methods_involved_in_recursive_call_chain(
            entry_point, resolve_dispatch,
            include_direct_recursive_calls=True)
        self.assertEqual(methods_ircc, [('B', rv('b')), ('C', rv('c'))])
        methods_ircc = cb.find_methods_involved_in_recursive_call_chain(
            entry_point, resolve_dispatch,
            include_direct_recursive_calls=False)
        self.assertEqual(methods_ircc, [('B', rv('b')), ('C', rv('c'))])

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
