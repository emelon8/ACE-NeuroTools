#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Jan  4 13:34:51 2025

@author: lukerichards
"""
from setuptools import setup, find_packages

setup(
    name='Experiment Analysis',
    version='0.1.0',
    packages=find_packages(),
    install_requires=[
        'numpy',
        'scipy',
    ],
    include_package_data=True,
)