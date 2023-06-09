### testing
"""
Created on Fri June 9 9:00:00 2023

@author: Rachael Fisher 

This script is used to crop within lens and find average fluorescence and compare with Ephys data, correlation and cross correlation metrics
"""
import miniscope 

channel = 'PFCEEGvsCBEEG'

obj = miniscope_ephys.miniscopeEphys(lineNum=lineNum)

obj.importEphysData(channels=channel)
obj.importNeuralynxEvents(analogSignalImported=True)
obj.syncNeuralynxMiniscopeTimestamps(channel=channel)

obj.findEphysIdxOfTTLEvents(channel=channel, CaEvents=False)

obj.filterEphys(channel=channel)

obj.ephys[channel][obj.ephysIdxAllTTLEvents]
