#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
setup.py for jira-cli
"""

__author__ = 'Sören König'
__email__ = 'soeren-koenig@freenet.de'

import sys
from setuptools import setup, find_packages
import jiracli

extra = {}
if sys.version_info >= (3, ):
    extra['use_2to3'] = True

setup(
    name='jira-cli',
    author=__author__,
    author_email=__email__,
    url='https://github.com/skoenig/jira-cli',
    license='MIT',
    version=jiracli.__version__,
    description='command line utility for interacting with jira',
    long_description=open('README.rst').read(),
    classifiers=[k for k in open('CLASSIFIERS').read().split('\n') if k],
    packages=find_packages(exclude=['ez_setup']),
    include_package_data=True,
    zip_safe=False,
    install_requires=['setuptools', 'termcolor'],
    entry_points={'console_scripts': ['jira-cli = jiracli.cli:main']},
    **extra
)
