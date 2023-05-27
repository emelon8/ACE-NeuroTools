# -*- coding: utf-8 -*-
"""
Created on Fri May 19 16:13:23 2023

@author: Eric
"""

import miniscope_ephys
import numpy as np
import matplotlib.pyplot as plt

experimentNum = 41
channel = 'PCvsPFCEEG'
startFreq = 0.5
endFreq = 4.0

#%% Load experiment and ephys data
obj = miniscope_ephys.miniscopeEphys(experimentNum)

obj.importEphysData(channels=channel)
obj.importNeuralynxEvents(analogSignalImported=True)


#%% Compute and plot the spectrograms
# Look for time periods with high slow wave power
h, ax = obj.computeSpectrogram(channel=channel, plotSpectrogram=True, plotEvents=False, windowLength=10)
ax.set_title(obj.experiment['line number'] + ': ' + obj.experiment['id'] + ', ' + obj.experiment['systemic drug'])


#%% Find high slow wave power
# After you have looked at the spectrograms and found areas that you think have high slow wave power, run this cell to plot the mean power in the slow wave band
bandStart = np.where(obj.freqsSpect>=startFreq)[0][0]
bandEnd = np.where(obj.freqsSpect<=endFreq)[0][-1]
meanBand = np.mean(obj.pSpect[bandStart:bandEnd+1,:],axis=0)
plt.figure()
plt.plot(obj.tSpect, meanBand)


#%% Find miniscope indices of high slow wave power
# Set the times of high slow wave power (periods with power higher than 62 dB, at least in experiment 35)
timeSecStart = obj._analysisParamsDict['periods of high slow wave power (s)'][0]
timeSecEnd = obj._analysisParamsDict['periods of high slow wave power (s)'][-1]

obj.syncNeuralynxMiniscopeTimestamps(channel=channel)
obj.findEphysIdxOfTTLEvents(channel=channel, CaEvents=False)


#%% Find the miniscope frames and videos corresponding to the high slow wave power
frameStart = np.where(obj.tEphys[channel][obj.ephysIdxAllTTLEvents]>timeSecStart)[0][0]
frameEnd = np.where(obj.tEphys[channel][obj.ephysIdxAllTTLEvents]<timeSecEnd)[0][-1]

print('The first video in the sequence is ' + str(int(np.ceil(frameStart/1000))) + '.avi.')
print('The last video in the sequence is ' + str(int(np.floor(frameEnd/1000)-1)) + '.avi.')