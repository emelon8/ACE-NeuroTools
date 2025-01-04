#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Jan  2 19:53:41 2025

@author: lukerichards
"""

from src.classes import miniscope_ephys

lineNum = 64
channel = 'PFCLFPvsCBEEG'


obj = miniscope_ephys.miniscopeEphys(lineNum) 
fr = obj.experiment['frameRate']
obj.importEphysData(channels=channel)
obj.importNeuralynxEvents()
obj.syncNeuralynxMiniscopeTimestamps(channel=channel)
obj.findEphysIdxOfTTLEvents(channel=channel, CaEvents=False)

obj.computeSpectrogram()
