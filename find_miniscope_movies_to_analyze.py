# -*- coding: utf-8 -*-
"""
Created on Fri May 19 16:13:23 2023

@author: Eric
"""

import miniscope_ephys

channel = 'PCvsPFCEEG'

obj = miniscope_ephys.miniscopeEphys(37)

obj.importEphysData(channels=channel)
obj.importNeuralynxEvents(analogSignalImported=False)

obj.computeSpectrogram(channel=channel, plotSpectrogram=True, plotEvents=False)

obj.syncNeuralynxMiniscopeTimestamps(channel=channel)
obj.findEphysIdxOfTTLEvents(CaEvents=False)

a = obj.tEphys[channel][obj.ephysIdxAllTTLEvents]-obj.tEphys[channel][obj.ephysIdxAllTTLEvents][0]

timeSec = 3600

t = np.where(a>timeSec)[0]