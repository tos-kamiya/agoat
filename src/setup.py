#!/usr/bin/env python2

from distutils.core import setup

setup(
    name='agoat',
    version="0.6.0",
    description='Java code-search tool',
    author='Toshihito Kamiya',
    url='https://github.com/tos-kamiya/agoat',
    packages=['agoat'],
    scripts=['ag-run-disasms', 'ag-i', 'ag-q'],
    requires=['colorama'],
    package_data={'': ['soot-2.5.0.jar']},
    license = 'MIT'
)