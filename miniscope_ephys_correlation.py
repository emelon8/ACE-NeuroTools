# -*- coding: utf-8 -*-
"""
Created on Tue Jul 25 17:27:39 2023

@author: Eric
"""

from scipy.signal import correlate, correlation_lags, coherence
import miniscope_ephys
import matplotlib.pyplot as plt
import numpy as np
import misc_functions

lineNum = 83
channel = 'PFCLFPvsCBEEG'

obj = miniscope_ephys.miniscopeEphys(lineNum)

obj.importEphysData(channels=[channel, 'PFCEEGvsCBEEG'])
obj.importNeuralynxEvents(analogSignalImported=True)
obj.syncNeuralynxMiniscopeTimestamps(channel=channel)
obj.findEphysIdxOfTTLEvents(channel=channel, CaEvents=False)

meanFluorescence = np.load('../../experimental_results/miniscope_ephys_correlation_project/npzFiles/meanFluorescence_' + str(lineNum) + '.npz')

fdataM = misc_functions.filterData(meanFluorescence['meanFluorescence'], n=2, cut=[1,3], ftype='butter', btype='bandpass', fs=obj.experiment['frameRate'])

obj.filterEphys(channel=channel, n=2, cut=[1,3], ftype='butter', inline=False)

obj.computeSpectrogram(freqLims=[0,15])
plt.gcf()
ax = plt.gca()
xl = ax.get_xlim()
obj.computeSpectrogram(channel='PFCEEGvsCBEEG', freqLims=[0,15])
obj.computeMiniscopeSpectrogram(meanFluorescence['meanFluorescence'])
plt.gcf()
ax3 = plt.gca()
ax3.set_xlim(xl)

# Times (s) to analyze based on the ephys spectrogram
begin = obj._analysisParamsDict['periods of high slow wave power (s)'][0]
end = obj._analysisParamsDict['periods of high slow wave power (s)'][1]

start = np.where(obj.tEphys[channel][obj.ephysIdxAllTTLEvents]>begin)[0][0]
stop = np.where(obj.tEphys[channel][obj.ephysIdxAllTTLEvents]>end)[0][0]

ephys = obj.fdata[0].data[obj.ephysIdxAllTTLEvents][start:stop]
minis = fdataM[start:stop]


# Calculate and plot the normalized cross-correlation
nminis = minis/np.max(np.abs(minis))
nephys = ephys/np.max(np.abs(ephys))
nxcorr = correlate(nminis, nephys)
nxcorrLags = correlation_lags(minis.size, ephys.size)
nlag = nxcorrLags[np.argmax(nxcorr)]

plt.figure()
plt.plot(nxcorrLags, nxcorr)
plt.title('Normalized cross-correlation')


# Calculate and plot the coherence