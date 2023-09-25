### testing
"""
Created on Fri June 9 9:00:00 2023

@author: Rachael Fisher 

This script is used to crop within lens and find average fluorescence and compare with Ephys data, correlation and cross correlation metrics.
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

meanFluorescence = np.load('/home/lab/Desktop/Correlation Project/npzFiles/meanFluorescence_'+ str(lineNum)+ '.npz')

fdataM = misc_functions.filterData(meanFluorescence['meanFluorescence'], n=2, cut=[1,3], ftype='butter', btype='bandpass', fs=fr)
obj.filterEphys(channel=channel, n=2, cut=[1,3], ftype='butter', inline=False)

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
nephys = ephys/np.std(ephys)
nxcorr = correlate(nminis, nephys) / nminis.size
nxcorrLags = correlation_lags(nminis.size, nephys.size) / fr
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

nminisControl = minisControl/np.std(minisControl)
nephysControl = ephysControl/np.std(ephysControl)
nxcorrControl = correlate(nminisControl, nephysControl) / nminisControl.size
nxcorrLagsControl = correlation_lags(nminisControl.size, nephysControl.size) / fr
nlagControl = nxcorrLagsControl[np.argmax(nxcorrControl)]

extremesCon = [np.max(nxcorrControl),np.min(nxcorrControl)]
extremesTimestampsCon  = [nxcorrLagsControl[np.argmax(nxcorrControl)],nxcorrLagsControl[np.argmin(nxcorrControl)]]

nacorrMinis = correlate(nminis, nminis) / nminis.size
nacorrLagsMinis = correlation_lags(nminis.size, nminis.size) / fr
nlag = nacorrLagsMinis[np.argmax(nacorrMinis)]

nacorrMinisControl = correlate(nminisControl, nminisControl) / nminisControl.size
nacorrLagsMinisControl = correlation_lags(nminisControl.size, nminisControl.size) / fr
nlagMinisControl = nacorrLagsMinisControl[np.argmax(nacorrMinisControl)]

nacorrEphys = correlate(nephys, nephys) / nephys.size
nacorrLagsEphys = correlation_lags(nephys.size, nephys.size) / fr
nlagEphys = nacorrLagsEphys[np.argmax(nacorrEphys)]

nacorrEphysControl = correlate(nephysControl, nephysControl) / nephysControl.size
nacorrLagsEphysControl = correlation_lags(nephysControl.size, nephysControl.size) / fr
nlagEphysControl = nacorrLagsEphysControl[np.argmax(nacorrEphysControl)]