# coding: utf-8

import unittest

import sys
import os.path
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))

import agoat.andor_tree as at
import agoat.jimp_parser as jp
import agoat.calltree_builder as cb


class ClassDataStubOnlyBase(object):
    def __init__(self, base_name):
        self.base_name = base_name
        self.interf_names = None


class ClassDataStubOnlyMethods(object):
    def __init__(self, class_name, methods):
        self.class_name = class_name
        self.methods = methods


class MethodDataStubOnlyCode(object):
    def __init__(self, clzmsig, code):
        self.clzmsig = clzmsig
        self.code = code


def crv(c, m):
    return c + '\tvoid\t' + m

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
        class_to_methods = {'A': [crv('A', 'a'), crv('A', 'b')], 'M': [crv('M', 'm'), crv('M', 'n')], 'P': [crv('P', 'p'), crv('P', 'q')]}
        class_to_descendants = {}
        recv_method_to_defs = cb.make_dispatch_table(class_to_methods, class_to_descendants)
        self.assertEqual(recv_method_to_defs, {
            ('A', mnamc('a')): [crv('A', 'a')],
            ('A', mnamc('b')): [crv('A', 'b')],
            ('M', mnamc('m')): [crv('M', 'm')],
            ('M', mnamc('n')): [crv('M', 'n')],
            ('P', mnamc('p')): [crv('P', 'p')],
            ('P', mnamc('q')): [crv('P', 'q')]
        })

    def test_resolve_dispatch_nooverride(self):
        class_to_methods = {'A': [crv('A', 'a'), crv('A', 'b')], 'M': [crv('M', 'm'), crv('M', 'n')], 'P': [crv('P', 'p'), crv('P', 'q')]}
        class_to_descendants = {'A': {'M': 1, 'P': 1}}
        recv_method_to_defs = cb.make_dispatch_table(class_to_methods, class_to_descendants)
        self.assertEqual(recv_method_to_defs, {
            ('A', mnamc('a')): [crv('A', 'a')],
            ('A', mnamc('b')): [crv('A', 'b')],
            ('M', mnamc('a')): [crv('A', 'a')],
            ('M', mnamc('b')): [crv('A', 'b')],
            ('M', mnamc('m')): [crv('M', 'm')],
            ('M', mnamc('n')): [crv('M', 'n')],
            ('P', mnamc('a')): [crv('A', 'a')],
            ('P', mnamc('b')): [crv('A', 'b')],
            ('P', mnamc('p')): [crv('P', 'p')],
            ('P', mnamc('q')): [crv('P', 'q')]
        })

    def test_resolve_dispatch_inheritance_override(self):
        class_to_methods = {'A': [crv('A', 'a'), crv('A', 'b')], 'M': [crv('M', 'b'), crv('M', 'm')], 'P': [crv('P', 'b'), crv('P', 'p')]}
        class_to_descendants = {'A': {'M': 1, 'P': 1}}
        recv_method_to_defs = cb.make_dispatch_table(class_to_methods, class_to_descendants)
        self.assertEqual(recv_method_to_defs, {
            ('A', mnamc('a')): [crv('A', 'a')],
            ('A', mnamc('b')): [crv('A', 'b'), crv('M', 'b'), crv('P', 'b')],
            ('M', mnamc('a')): [crv('A', 'a')],
            ('M', mnamc('b')): [crv('M', 'b')],
            ('M', mnamc('m')): [crv('M', 'm')],
            ('P', mnamc('a')): [crv('A', 'a')],
            ('P', mnamc('b')): [crv('P', 'b')],
            ('P', mnamc('p')): [crv('P', 'p')]
        })

        class_to_descendants = {'A': {'M':1, 'P': 2}, 'M': {'P': 1}}
        recv_method_to_defs = cb.make_dispatch_table(class_to_methods, class_to_descendants)
        self.assertEqual(recv_method_to_defs, {
            ('A', mnamc('a')): [crv('A', 'a')], 
            ('A', mnamc('b')): [crv('A', 'b'), crv('M', 'b'), crv('P', 'b')],
            ('M', mnamc('a')): [crv('A', 'a')], 
            ('M', mnamc('b')): [crv('M', 'b'), crv('P', 'b')], 
            ('M', mnamc('m')): [crv('M', 'm')],
            ('P', mnamc('a')): [crv('A', 'a')], 
            ('P', mnamc('m')): [crv('M', 'm')],
            ('P', mnamc('b')): [crv('P', 'b')], 
            ('P', mnamc('p')): [crv('P', 'p')]
        })

    def test_find_methods_involved_in_recursive_call_chain_direct(self):
        class_table = {
            'A': ClassDataStubOnlyMethods('A', {
                crv('A', 'main'): MethodDataStubOnlyCode(crv('Main', 'main'), [at.ORDERED_AND,
                    (jp.INVOKE, crv('B', 'b'))
                ])
            }),
            'B': ClassDataStubOnlyMethods('B', {
                crv('B', 'b'): MethodDataStubOnlyCode(crv('B', 'b'), [at.ORDERED_AND,
                    (jp.INVOKE, crv('B', 'b'))
                ])
            }),
        }
        class_to_descendants = {}
        recv_method_to_defs = {
            ('A', mnamc('main')): [crv('A', 'main')],
            ('B', mnamc('b')): [crv('B', 'b')],
        }
        resolve_dispatch = cb.gen_method_dispatch_resolver(class_table, class_to_descendants, recv_method_to_defs)
        entry_point = crv('A', 'main')
        methods_ircc = cb.find_methods_involved_in_recursive_call_chain(
            entry_point, resolve_dispatch,
            include_direct_recursive_calls=True)
        self.assertEqual(methods_ircc, [crv('B', 'b')])
        methods_ircc = cb.find_methods_involved_in_recursive_call_chain(
            entry_point, resolve_dispatch,
            include_direct_recursive_calls=False)
        self.assertEqual(methods_ircc, [])
 
    def test_find_methods_involved_in_recursive_call_chain_indirect(self):
        class_table = {
            'A': ClassDataStubOnlyMethods('A', {
                crv('A', 'main'): MethodDataStubOnlyCode(crv('A', 'main'), [at.ORDERED_AND,
                    (jp.INVOKE, crv('B', 'b'))
                ])
            }),
            'B': ClassDataStubOnlyMethods('B', {
                crv('B', 'b'): MethodDataStubOnlyCode(crv('B', 'b'), [at.ORDERED_AND,
                    (jp.INVOKE, crv('C', 'c'))
                ])
            }),
            'C': ClassDataStubOnlyMethods('C', {
                crv('C', 'c'): MethodDataStubOnlyCode(crv('C', 'c'), [at.ORDERED_AND,
                    (jp.INVOKE, crv('B', 'b'))
                ])
            }),
        }
        recv_method_to_defs = {
            ('A', mnamc('main')): [crv('A', 'main')],
            ('B', mnamc('b')): [crv('B', 'b')],
            ('C', mnamc('c')): [crv('C', 'c')],
        }
        class_to_descendants = {}
        resolve_dispatch = cb.gen_method_dispatch_resolver(class_table, class_to_descendants, recv_method_to_defs)
        entry_point = crv('A', 'main')
        methods_ircc = cb.find_methods_involved_in_recursive_call_chain(
            entry_point, resolve_dispatch,
            include_direct_recursive_calls=True)
        self.assertEqual(methods_ircc, [crv('B', 'b'), crv('C', 'c')])
        methods_ircc = cb.find_methods_involved_in_recursive_call_chain(
            entry_point, resolve_dispatch,
            include_direct_recursive_calls=False)
        self.assertEqual(methods_ircc, [crv('B', 'b'), crv('C', 'c')])


stub_class_to_descendants = { 
    "A": { "B": 1, "C": 2}, 
    "B": { "C": 1 } 
}


class CalltreeBuilderFuncTest(unittest.TestCase):
    def test_java_is_a_void(self):
        self.assertEqual(cb.java_is_a(None, None, stub_class_to_descendants), 0)
        self.assertEqual(cb.java_is_a(None, "null", stub_class_to_descendants), -1)
        self.assertEqual(cb.java_is_a("null", None, stub_class_to_descendants), -1)
        self.assertEqual(cb.java_is_a(None, "int", stub_class_to_descendants), -1)
        self.assertEqual(cb.java_is_a(None, "java.lang.Object", stub_class_to_descendants), -1)

    def test_java_is_a_null(self):
        self.assertEqual(cb.java_is_a("null", "null", stub_class_to_descendants), 0)
        self.assertEqual(cb.java_is_a("null", "java.lang.Object", stub_class_to_descendants), 0)
        self.assertEqual(cb.java_is_a("null", "char", stub_class_to_descendants), -1)

    def test_java_is_a_class(self):
        self.assertEqual(cb.java_is_a("A", "A", stub_class_to_descendants), 0)
        self.assertEqual(cb.java_is_a("A", "B", stub_class_to_descendants), -1)
        self.assertEqual(cb.java_is_a("B", "A", stub_class_to_descendants), 1)
        self.assertEqual(cb.java_is_a("C", "A", stub_class_to_descendants), 2)

    def test_java_is_a_array(self):
        self.assertEqual(cb.java_is_a("A[]", "A", stub_class_to_descendants), -1)
        self.assertEqual(cb.java_is_a("A[]", "B[]", stub_class_to_descendants), -1)
        self.assertEqual(cb.java_is_a("B[]", "A[]", stub_class_to_descendants), 1)
        self.assertEqual(cb.java_is_a("C[]", "A[]", stub_class_to_descendants), 2)

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
