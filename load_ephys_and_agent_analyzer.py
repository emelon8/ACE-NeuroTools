#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Nov 30 12:14:48 2023

@author: lab
"""

import ephys
import matplotlib.pyplot as plt

obj = ephys.NeuralynxEphys(107)

obj.importAgentAnalyzerData()

# obj.importEphysData()
