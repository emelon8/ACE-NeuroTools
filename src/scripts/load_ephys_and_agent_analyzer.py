#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Nov 30 12:14:48 2023

@author: lab
"""

import miniscope_ephys
import matplotlib.pyplot as plt

obj = miniscope_ephys.miniscopeEphys(107)

obj.importEphysData()

obj.importNeuralynxEvents(analogSignalImported=True)

obj.importAgentAnalyzerData()

h, ax = obj.computeSpectrogram(channel='PFCEEGvsCBEEG')

ax2 = h.add_subplot(2,1,2) #this doesn't do what you want. see https://gist.github.com/LeoHuckvale/89683dc242f871c8e69b
ax2.set_ylabel('Isoflurane concentration (%)')
ax2.plot(obj.agentAnalyzer['AA_FI'])