# -*- coding: utf-8 -*-
"""
Created on Tue Jul 25 17:27:39 2023

@author: Eric
"""

from scipy.signal import correlate, correlation_lags, coherence
from scipy.stats import pearsonr
import miniscope_ephys
import matplotlib.pyplot as plt
import numpy as np
import misc_functions

lineNum = 47
channel = 'PFCLFPvsCBEEG'

obj = miniscope_ephys.miniscopeEphys(lineNum)
fr = obj.experiment['frameRate']
obj.importEphysData(channels=[channel, 'PFCEEGvsCBEEG'])
obj.importNeuralynxEvents(analogSignalImported=True)
obj.syncNeuralynxMiniscopeTimestamps(channel=channel)
obj.findEphysIdxOfTTLEvents(channel=channel, CaEvents=False)

drug = obj.experiment['systemic drug']
rat = obj.experiment['animalID']

#meanFluorescence = np.load('../../experimental_results/miniscope_ephys_correlation_project/npzFiles/meanFluorescence_' + str(lineNum) + '.npz')
meanFluorescence = np.load('/home/lab/Desktop/Correlation Project/npzFiles/meanFluorescence_'+ str(lineNum)+ '.npz')

fdataM = misc_functions.filterData(meanFluorescence['meanFluorescence'], n=2, cut=[1,3], ftype='butter', btype='bandpass', fs=fr)
obj.filterEphys(channel=channel, n=2, cut=[1,3], ftype='butter', inline=False)

obj.computeSpectrogram(freqLims=[0,15], channel = channel, windowLength=10, windowStep=1)
plt.gcf()
ax = plt.gca()
xl = ax.get_xlim()
ax.set_title('PFC LFP spectrogram, Exp. ' + str(lineNum))
obj.computeSpectrogram(channel='PFCEEGvsCBEEG', freqLims=[0,15], windowLength=10, windowStep=1)
plt.gcf()
ax2 = plt.gca()
ax2.set_title('PFC EEG spectrogram, Exp. ' + str(lineNum))
obj.computeMiniscopeSpectrogram(meanFluorescence['meanFluorescence'], windowLength=10, windowStep=1)
plt.gcf()
ax3 = plt.gca()
ax3.set_xlim(xl)
ax3.set_title('Miniscope spectrogram, Exp. ' + str(lineNum))

# Times (s) to analyze based on the ephys spectrogram
begin = obj._analysisParamsDict['periods of high slow wave power (s)'][0]
end = obj._analysisParamsDict['periods of high slow wave power (s)'][1]
beginControl = obj._analysisParamsDict['control periods (s)'][0]
endControl = obj._analysisParamsDict['control periods (s)'][1]

start = np.where(obj.tEphys[channel][obj.ephysIdxAllTTLEvents]>begin)[0][0]
stop = np.where(obj.tEphys[channel][obj.ephysIdxAllTTLEvents]>end)[0][0]
startControl = np.where(obj.tEphys[channel][obj.ephysIdxAllTTLEvents]>beginControl)[0][0]
stopControl = np.where(obj.tEphys[channel][obj.ephysIdxAllTTLEvents]>endControl)[0][0]

ephys = obj.fdata[0].data[obj.ephysIdxAllTTLEvents][start:stop]
minis = fdataM[start:stop]
ephysControl = obj.fdata[0].data[obj.ephysIdxAllTTLEvents][startControl:stopControl]
minisControl = fdataM[startControl:stopControl]


# Calculate and plot the normalized cross-correlation
nminis = minis/np.std(minis)
nminis_centered = nminis - np.average(nminis)
nephys = ephys/np.std(ephys)
nephys_centered = nephys - np.average(nephys)
nxcorr = correlate(nminis_centered, nephys_centered) / nminis_centered.size
nxcorrLags = correlation_lags(nminis_centered.size, nephys_centered.size) / fr
nlag = nxcorrLags[np.argmax(nxcorr)]

extremes = [np.max(nxcorr),np.min(nxcorr)]
extremesTimestamps = [nxcorrLags[np.argmax(nxcorr)],nxcorrLags[np.argmin(nxcorr)]]

if np.max(nxcorr) >= abs(np.min(nxcorr)):
     xlimitLeft = nxcorrLags[np.argmax(nxcorr)] - 2
     xlimitRight = nxcorrLags[np.argmax(nxcorr)] + 2
     print('The maximum normalized cross correlation of for the experimental period is ' + str(np.max(nxcorr)) + ' at time ' +  str(nxcorrLags[np.argmax(nxcorr)]) + ' seconds')
else:
     xlimitLeft = nxcorrLags[np.argmin(nxcorr)] - 2
     xlimitRight = nxcorrLags[np.argmin(nxcorr)] + 2
     print('The minimum normalized cross correlation of for the experimental period is ' + str(np.min(nxcorr)) + ' at time ' +  str(nxcorrLags[np.argmin(nxcorr)])+ ' seconds')


plt.figure(num=4)
plt.plot(nxcorrLags, nxcorr)
plt.title('Normalized cross-correlation, Exp. ' + str(lineNum))
#plt.xlim([-2, 2])
plt.xlim([xlimitLeft, xlimitRight])
plt.ylim([-1.1,1.1])

nminisControl = minisControl/np.std(minisControl)
nminisControlCentered = nminisControl - (np.average(nminisControl))
nephysControl = ephysControl/np.std(ephysControl)
nephysControlCentered = nephysControl - (np.average(nephysControl))
nxcorrControl = correlate(nminisControlCentered, nephysControlCentered) / nminisControlCentered.size
nxcorrLagsControl = correlation_lags(nminisControlCentered.size, nephysControlCentered.size) / fr
nlagControl = nxcorrLagsControl[np.argmax(nxcorrControl)]

extremesCon = [np.max(nxcorrControl),np.min(nxcorrControl)]
extremesTimestampsCon  = [nxcorrLagsControl[np.argmax(nxcorrControl)],nxcorrLagsControl[np.argmin(nxcorrControl)]]

plt.figure(num=5)
plt.plot(nxcorrLagsControl, nxcorrControl)
plt.title('Normalized cross-correlation, control period, Exp. ' + str(lineNum))
#plt.xlim([-2, 2])
plt.xlim([xlimitLeft, xlimitRight])
plt.ylim([-1.1,1.1])

# Calculate and plot the normalized auto-correlation
nacorrMinis = correlate(nminis_centered, nminis_centered) / nminis_centered.size
nacorrLagsMinis = correlation_lags(nminis_centered.size, nminis_centered.size) / fr
nlag = nacorrLagsMinis[np.argmax(nacorrMinis)]

plt.figure(num=6)
plt.plot(nacorrLagsMinis, nacorrMinis)
plt.title('Miniscope normalized auto-correlation, Exp. ' + str(lineNum))
plt.xlim([-2, 2])
plt.ylim([-1.1,1.1])

nacorrMinisControl = correlate(nminisControlCentered, nminisControlCentered) / nminisControlCentered.size
nacorrLagsMinisControl = correlation_lags(nminisControlCentered.size, nminisControlCentered.size) / fr
nlagMinisControl = nacorrLagsMinisControl[np.argmax(nacorrMinisControl)]

plt.figure(num=7)
plt.plot(nacorrLagsMinisControl, nacorrMinisControl)
plt.title('Miniscope normalized auto-correlation, control period, Exp. ' + str(lineNum))
plt.xlim([-2, 2])
plt.ylim([-1.1,1.1])

nacorrEphys = correlate(nephys_centered, nephys_centered) / nephys_centered.size
nacorrLagsEphys = correlation_lags(nephys_centered.size, nephys_centered.size) / fr
nlagEphys = nacorrLagsEphys[np.argmax(nacorrEphys)]

plt.figure(num=8)
plt.plot(nacorrLagsEphys, nacorrEphys)
plt.title('LFP normalized auto-correlation, Exp. ' + str(lineNum))
plt.xlim([-2, 2])
plt.ylim([-1.1,1.1])

nacorrEphysControl = correlate(nephysControlCentered, nephysControlCentered) / nephysControlCentered.size
nacorrLagsEphysControl = correlation_lags(nephysControlCentered.size, nephysControlCentered.size) / fr
nlagEphysControl = nacorrLagsEphysControl[np.argmax(nacorrEphysControl)]

plt.figure(num=9)
plt.plot(nacorrLagsEphysControl, nacorrEphysControl)
plt.title('LFP normalized auto-correlation, control period, Exp. ' + str(lineNum))
plt.xlim([-2, 2])
plt.ylim([-1.1,1.1])

# Calculate and plot the coherence
plt.figure(num=10)
plt.cohere(nminis_centered,nephys_centered,Fs=30)
plt.title('Coherence of miniscope fluorescence and ephys, Exp. ' + str(lineNum))
plt.ylim([-1.1,1.1])

plt.figure(num=11)
plt.cohere(nminisControlCentered,nephysControlCentered,Fs=30)
plt.title('Coherence of miniscope fluorescence and ephys, control period, Exp. ' + str(lineNum))
plt.ylim([-1.1,1.1])

R1, P1 = pearsonr(nminis_centered, nephys_centered)

R2, P2 = pearsonr(nminisControlCentered, nephysControlCentered)

data = [lineNum, rat, drug, extremes[0], extremesTimestamps[0], extremes[1], extremesTimestamps[1], extremesCon[0], extremesTimestampsCon[0], extremesCon[1], extremesTimestampsCon[1]]
