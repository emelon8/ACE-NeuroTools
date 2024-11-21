# -*- coding: utf-8 -*-
"""
Created on Tue Jul 25 17:27:39 2023

@author: Eric
"""
#%%  #packages needed
from scipy.signal import correlate, correlation_lags, coherence
from scipy.stats import pearsonr
import miniscope_ephys
import matplotlib.pyplot as plt
import numpy as np
import misc_functions
import pandas as pd


#%%  #experiment selection and channels
lineNum = 46
channel = 'PFCLFPvsCBEEG'

obj = miniscope_ephys.miniscopeEphys(lineNum)
fr = obj.experiment['frameRate']
obj.importEphysData(channels=[channel, 'PFCEEGvsCBEEG'])
obj.importNeuralynxEvents()
obj.syncNeuralynxMiniscopeTimestamps(channel=channel)
obj.findEphysIdxOfTTLEvents(channel=channel)


#%%  #dataframe setup if exporting data
df_centered = pd.DataFrame(columns=['experiment', 'rat', 'drug', 'MPE', 'MPELag', 'MNE', 'MNELag', 'MPC', 'MPCLag', 'MNC', 'MNCLag', 'expR', 'expP', 'conR', 'conP', 'exp coher', 'exp freq', 'con coher', 'con freq'])
drug = obj.experiment['systemic drug']
rat = obj.experiment['animalID']


#%% #data importing 
meanFluorescence = np.load('/home/lab/Desktop/Correlation Project/npzFiles/meanFluorescence_'+ str(lineNum)+ '.npz')
fdataM = misc_functions.filterData(meanFluorescence['meanFluorescence'], n=2, cut=[1,3], ftype='butter', btype='bandpass', fs=fr)
obj.filterEphys(channel=channel, n=2, cut=[1,3], ftype='butter', inline=False)


#%% #spectrograms
obj.computeSpectrogram(freqLims=[0,15], channel = channel, windowLength=10, windowStep=1)
plt.gcf()
ax = plt.gca()
xl = ax.get_xlim()
ax.set_title('PFC LFP spectrogram, Exp. ' + str(lineNum) + ', ' + channel )
obj.computeSpectrogram(channel='PFCEEGvsCBEEG', freqLims=[0,15], windowLength=10, windowStep=1)
plt.gcf()
ax2 = plt.gca()
ax2.set_title('PFC EEG spectrogram, Exp. ' + str(lineNum))
obj.computeMiniscopeSpectrogram(meanFluorescence['meanFluorescence'], windowLength=10, windowStep=1)
plt.gcf()
ax3 = plt.gca()
ax3.set_xlim(xl)
ax3.set_title('Miniscope spectrogram, Exp. ' + str(lineNum))


#%%
# Times (s) to analyze based on the ephys spectrogram
begin = obj._analysisParamsDict['periods of high slow wave power (s)'][0]
end = obj._analysisParamsDict['periods of high slow wave power (s)'][1]
beginControl = obj._analysisParamsDict['control periods (s)'][0]
endControl = obj._analysisParamsDict['control periods (s)'][1]

start = np.where(obj.tEphys[channel][obj.ephysIdxAllTTLEvents]>begin)[0][0]
stop = np.where(obj.tEphys[channel][obj.ephysIdxAllTTLEvents]>end)[0][0]
startControl = np.where(obj.tEphys[channel][obj.ephysIdxAllTTLEvents]>beginControl)[0][0]
stopControl = np.where(obj.tEphys[channel][obj.ephysIdxAllTTLEvents]>endControl)[0][0]


#%% 
# Calculate and plot the coherence
plt.figure(num=4)
original, freqs = plt.cohere(meanFluorescence['meanFluorescence'][start:stop],obj.ephys[channel][obj.ephysIdxAllTTLEvents][start:stop],Fs=30)
plt.title('Coherence of experimental miniscope fluorescence and ephys (original), Exp. ' + str(lineNum))
coherMax = np.max(original)
maxFreq = freqs[np.argmax(original)]

plt.figure(num=5)
originalCon, freqs2 = plt.cohere(meanFluorescence['meanFluorescence'][startControl:stopControl],obj.ephys[channel][obj.ephysIdxAllTTLEvents][startControl:stopControl], Fs = 30)
plt.title('Coherence of miniscope fluorescence and ephys, control period, Exp. ' + str(lineNum))
coherMaxCon = np.max(originalCon)
maxFreqCon = freqs2[np.argmax(originalCon)]


#%% 
ephys = obj.fdata[0].data[obj.ephysIdxAllTTLEvents][start:stop]
minis = fdataM[start:stop]
ephysControl = obj.fdata[0].data[obj.ephysIdxAllTTLEvents][startControl:stopControl]
minisControl = fdataM[startControl:stopControl]

# Calculate and plot the normalized cross-correlation
nminis = minis/np.std(minis)
nephys = ephys/np.std(ephys)
nxcorr = correlate(nephys, nminis) / nephys.size
nxcorrLags = correlation_lags(nephys.size, nminis.size) / fr
nlag = nxcorrLags[np.argmax(nxcorr)]


#%% 
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


#%% 
plt.figure(num=6)
plt.plot(nxcorrLags, nxcorr)
plt.title('Normalized cross-correlation, Exp. ' + str(lineNum))
plt.xlabel('time lag (s)')
plt.ylabel('cross-correlation')
#plt.xlim([-2, 2])
plt.xlim([xlimitLeft, xlimitRight])
plt.ylim([-1.1,1.1])


#%% 
#control data
nminisControl = minisControl/np.std(minisControl)
nephysControl = ephysControl/np.std(ephysControl)
nxcorrControl = correlate(nephysControl, nminisControl) / nephysControl.size
nxcorrLagsControl = correlation_lags(nephysControl.size, nminisControl.size) / fr
nlagControl = nxcorrLagsControl[np.argmax(nxcorrControl)]

extremesCon = [np.max(nxcorrControl),np.min(nxcorrControl)]
extremesTimestampsCon  = [nxcorrLagsControl[np.argmax(nxcorrControl)],nxcorrLagsControl[np.argmin(nxcorrControl)]]


#%% 
#auto correlations
plt.figure(num=7)
plt.plot(nxcorrLagsControl, nxcorrControl)
plt.title('Normalized cross-correlation, control period, Exp. ' + str(lineNum))
plt.xlabel('time lag (s)')
plt.ylabel('cross-correlation')
#plt.xlim([-2, 2])
plt.xlim([xlimitLeft, xlimitRight])
plt.ylim([-1.1,1.1])


#%% Calculate and plot the normalized auto-correlation
nacorrMinis = correlate(nminis, nminis) / nminis.size
nacorrLagsMinis = correlation_lags(nminis.size, nminis.size) / fr
nlag = nacorrLagsMinis[np.argmax(nacorrMinis)]

plt.figure(num=8)
plt.plot(nacorrLagsMinis, nacorrMinis)
plt.title('Miniscope normalized auto-correlation, Exp. ' + str(lineNum))
plt.xlim([-2, 2])
plt.ylim([-1.1,1.1])

nacorrMinisControl = correlate(nminisControl, nminisControl) / nminisControl.size
nacorrLagsMinisControl = correlation_lags(nminisControl.size, nminisControl.size) / fr
nlagMinisControl = nacorrLagsMinisControl[np.argmax(nacorrMinisControl)]

plt.figure(num=9)
plt.plot(nacorrLagsMinisControl, nacorrMinisControl)
plt.title('Miniscope normalized auto-correlation, control period, Exp. ' + str(lineNum))
plt.xlim([-2, 2])
plt.ylim([-1.1,1.1])

nacorrEphys = correlate(nephys, nephys) / nephys.size
nacorrLagsEphys = correlation_lags(nephys.size, nephys.size) / fr
nlagEphys = nacorrLagsEphys[np.argmax(nacorrEphys)]

plt.figure(num=10)
plt.plot(nacorrLagsEphys, nacorrEphys)
plt.title('LFP normalized auto-correlation, Exp. ' + str(lineNum))
plt.xlim([-2, 2])
plt.ylim([-1.1,1.1])

nacorrEphysControl = correlate(nephysControl, nephysControl) / nephysControl.size
nacorrLagsEphysControl = correlation_lags(nephysControl.size, nephysControl.size) / fr
nlagEphysControl = nacorrLagsEphysControl[np.argmax(nacorrEphysControl)]

plt.figure(num=11)
plt.plot(nacorrLagsEphysControl, nacorrEphysControl)
plt.title('LFP normalized auto-correlation, control period, Exp. ' + str(lineNum))
plt.xlim([-2, 2])
plt.ylim([-1.1,1.1])


#%% 
#pearson data
R1, P1 = pearsonr(nminis, nephys)

R2, P2 = pearsonr(nminisControl, nephysControl)


#%% #adding data to df 
data = [lineNum, rat, drug, extremes[0], extremesTimestamps[0], extremes[1], extremesTimestamps[1], extremesCon[0], extremesTimestampsCon[0], extremesCon[1], extremesTimestampsCon[1], R1, P2, R2, P2]


#%% 
plt.figure(num = 12)
plt.plot(obj.tEphys[channel][obj.ephysIdxAllTTLEvents][start:stop], nminis, color = 'r', label = 'Miniscope')
### These lines were commented out of this file in Rachael's version, but I need to look at why.
# plt.plot(obj.tEphys[channel][obj.ephysIdxAllTTLEvents][start:stop], nephys, color = 'b', label = 'Ephys')
# plt.title('Overlapping trace of experimental miniscope fluorescence and ephys, Exp. ' + str(lineNum))
# plt.ylabel('Normalized traces')
# plt.xlabel('Time (s)')
# plt.legend()

# plt.figure(num = 13)
# plt.plot(nxcorrLags, nxcorr, color = 'r', label = 'Experimental')
###
plt.plot(obj.tEphys[channel][obj.ephysIdxAllTTLEvents][start:stop], nephys, color = 'b', label = 'Ephys')
plt.title('Overlapping trace of experimental miniscope fluorescence and ephys, Exp. ' + str(lineNum))
plt.ylabel('Normalized traces')
plt.xlabel('Time (s)')
plt.legend()