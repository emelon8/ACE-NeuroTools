# -*- coding: utf-8 -*-
"""
Created on Fri May 19 12:05:51 2023

@author: Eric

This script goes through the entire pipeline of data analysis to find the
phases of calcium events in simultaneous ephys and calcium imaging experiments.
"""

import miniscope_ephys

experiments = [35]
channel = 'PFCLFPvsCBEEG'

for k in experiments:
    obj = miniscope_ephys.miniscopeEphys(35)
    obj.importNeuralynxEvents(analogSignalImported=True)
    obj.importEphysData(channels=channel)
    obj.syncNeuralynxMiniscopeTimestamps(channel=channel)
    obj.computeSpectrogram(channel=channel, plotSpectrogram=True, plotEvents=False)
    obj.findEphysIdxOfTTLEvents(CaEvents=False)