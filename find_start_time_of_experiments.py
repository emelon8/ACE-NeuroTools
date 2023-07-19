# -*- coding: utf-8 -*-
"""
Created on Tue Jul 11 10:45:11 2023

@author: Eric

This script finds the start times of UCLA Miniscope and/or Neuralynx ephys recordings.
"""

import miniscope_ephys
from datetime import datetime

lineNum = 45

obj = miniscope_ephys.miniscopeEphys(lineNum)
# obj.importEphysData(channels='PFCLFPvsCBEEG')
obj.importNeuralynxEvents(analogSignalImported=False)
# obj.syncNeuralynxMiniscopeTimestamps()

ephysTimeIdx = [n for n, l in enumerate(obj.NeuralynxEvents['labels']) if l.startswith('time ')]
print('Neuralynx ephys recording started at ' + obj.NeuralynxEvents['labels'][ephysTimeIdx[0]][5:] + '.')

miniscopeStartTime = datetime.fromtimestamp(obj.experiment['recordingStartTime']['msecSinceEpoch']/1000)
print('UCLA Miniscope recording started at ' + str(miniscopeStartTime) + '.')