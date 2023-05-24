# -*- coding: utf-8 -*-
"""
Created on Fri May 19 16:13:23 2023

@author: Eric
"""

import miniscope_ephys
import numpy as np

channel = 'PCvsPFCEEG'

for k in [35, 42, 48, 37, 39, 41, 38, 45, 40]:
    obj = miniscope_ephys.miniscopeEphys(k)
    
    obj.importEphysData(channels=channel)
    # obj.importNeuralynxEvents(analogSignalImported=False)
    
    h, ax = obj.computeSpectrogram(channel=channel, plotSpectrogram=True, plotEvents=False, windowLength=10)
    ax.set_title(obj.experiment['line number'] + ': ' + obj.experiment['id'] + ', ' + obj.experiment['systemic drug'])
    
    # obj.syncNeuralynxMiniscopeTimestamps(channel=channel)
    # obj.findEphysIdxOfTTLEvents(CaEvents=False)
    
    # a = obj.tEphys[channel][obj.ephysIdxAllTTLEvents]-obj.tEphys[channel][obj.ephysIdxAllTTLEvents][0]
    
    # timeSec = 3600
    
    # t = np.where(a>timeSec)[0]