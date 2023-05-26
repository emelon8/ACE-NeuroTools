# -*- coding: utf-8 -*-
"""
Created on Fri May 19 16:13:23 2023

@author: Eric
"""

import miniscope_ephys
import numpy as np

channel = 'PCvsPFCEEG'
startFreq = 0.5
endFreq = 4.0

obj = []

for q, k in enumerate([35, 42, 48, 37, 39, 41, 38, 45, 40]):
#%% Load experiment and ephys data
    obj.append(miniscope_ephys.miniscopeEphys(k))
    
    obj[q].importEphysData(channels=channel)
    # obj[q].importNeuralynxEvents(analogSignalImported=False)
    
    
#%% Compute and plot the spectrograms
    h, ax = obj[q].computeSpectrogram(channel=channel, plotSpectrogram=True, plotEvents=False, windowLength=10)
    ax.set_title(obj[q].experiment['line number'] + ': ' + obj[q].experiment['id'] + ', ' + obj[q].experiment['systemic drug'])
    
    
#%% Find high slow wave power
    # After you have looked at the spectrograms and found areas that you think have high slow wave power, run the next cell to plot the mean power in the slow wave band
    bandStart = np.where(obj[q].freqsSpect>=startFreq)[0]
    bandEnd = np.where(obj[q].freqSpect<=endFreq)[0]
    meanBand = np.mean(obj[q].pSpect[bandStart:bandEnd+1,:],axis=0)
    
    
#%% Find miniscope indices of high slow wave power
    timeSecStart = 5861
    timeSecEnd = 6251
    
    obj[q].syncNeuralynxMiniscopeTimestamps(channel=channel)
    obj[q].findEphysIdxOfTTLEvents(CaEvents=False)
    
    a = obj[q].tEphys[channel][obj[q].ephysIdxAllTTLEvents]-obj[q].tEphys[channel][obj[q].ephysIdxAllTTLEvents][0]
    
    tStart = np.where(a>timeSecStart)[0]
    tEnd = np.where(a<timeSecEnd)[0]