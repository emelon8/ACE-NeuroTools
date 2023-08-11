### testing
"""
Created on Fri June 9 9:00:00 2023

@author: Rachael Fisher 

This script is used to crop within lens and find average fluorescence and compare with Ephys data, correlation and cross correlation metrics.
"""
import miniscope_ephys
import misc_functions
import numpy as np
from pylab import *
from scipy.signal import butter, freqz, filtfilt, firwin, bode
import matplotlib.pyplot as plt

#load data
lineNum = 43
channel ='PFCLFPvsCBEEG'

obj = miniscope_ephys.miniscopeEphys(lineNum)

obj.importEphysData()
obj.importNeuralynxEvents(analogSignalImported=True)
obj.syncNeuralynxMiniscopeTimestamps()
obj.findEphysIdxOfTTLEvents(CaEvents=False)

#if videos have already been analyzed, insert path  
meanFluorescence_43 = np.load('')

#for if npz file not created yet
obj.computeProjections(time = True)
# for loading and cropping all calcium videos 
numMovies = int(np.ceil(len(obj.timeStamps)/1000)) # The total number of calcium movie files

for i in range(numMovies):
    obj.importCaMovies(os.path.join(obj.experiment['calcium imaging directory'], 'Miniscope', str(i) + '.avi'))
    obj.preprocessCaMovies(saveMovie=True, crop=True, cropGUI=False, square=square)

# unfiltered calcium = obj.projections["time"]

#filter miniscope data... artifact removal?
fdataM = misc_functions.filterData(meanFluorescence_43['meanFluorescence'], n=2, cut=[1,3], ftype='butter', btype='bandpass', fs=obj.experiment['frameRate'])

#EEG DATA
obj.artifactRemoval(channel = channel, VThreshold=1600) # VThreshold will change based on exp
obj.filterEphys(channel = channel, n=2, cut=[1,3],ftype='butter',inline=False)

#control periods
conTimeSecStart = obj._analysisParamsDict['control periods (s)'][0]
conTimeSecEnd = obj._analysisParamsDict['control periods (s)'][-1]
conFrameStart = np.where(obj.tEphys[channel][obj.ephysIdxAllTTLEvents]>conTimeSecStart)[0][0]
conFrameEnd = np.where(obj.tEphys[channel][obj.ephysIdxAllTTLEvents]<conTimeSecEnd)[0][-1]
sliced = fdataM[conFrameStart:conFrameEnd]
conEphysData = obj.ephys[channel][obj.ephysIdxAllTTLEvents][conFrameStart:conFrameEnd]
conTEphysData = obj.tEphys[channel][obj.ephysIdxAllTTLEvents][conFrameStart:conFrameEnd]

conCorr = signal.correlate(sliced, ephysData, mode='full', method='auto')
normConCorr = conCorr / (len(sliced)*np.std(sliced)* np.std(conEphysData))

plt.figure()
plt.plot(normConCorr)

#experimental periods
exptimeSecStart = obj._analysisParamsDict['periods of high slow wave power (s)'][0]
exptimeSecEnd = obj._analysisParamsDict['periods of high slow wave power (s)'][-1]
expframeStart = np.where(obj.tEphys[channel][obj.ephysIdxAllTTLEvents]>exptimeSecStart)[0][0]
expframeEnd = np.where(obj.tEphys[channel][obj.ephysIdxAllTTLEvents]<exptimeSecEnd)[0][-1]
____________________________________________________________________________________________________________________________________________________________________________________

obj.filterMiniscope(inline = False)
filteredCalcium = obj.fdata[0].data

zscoreCa = (filteredCalcium - np.mean(filteredCalcium)) / np.std(filteredCalcium)
normalizedCa1 = filteredCalcium/np.max(filteredCalcium) 
normalizedCa2 = (filteredCalcium - np.min(filteredCalcium))/ np.ptp(filteredCalcium) # zero to one


filteredEphys = obj.fdata[1].data[obj.ephysIdxAllTTLEvents[0:len(filteredCalcium)]] #prints array of filtered data
unfilteredEphys = obj.ephys[channel][obj.ephysIdxAllTTLEvents[0:len(filteredCalcium)]]

zscoreEphys = (filteredEphys - np.mean(filteredEphys)) / np.std(filteredEphys)
normalized1Ephys = filteredEphys/np.max(filteredEphys) 
normalized2Ephys = (filteredEphys - np.min(filteredEphys))/ np.ptp(filteredEphys) # zero to one

timestamps = obj.tEphys[channel][obj.ephysIdxAllTTLEvents[0:len(filteredCalcium)]]

plt.plot(timestamps, normalized1Ephys)
plt.plot(timestamps, normalizedCa1)
plt.show()