### testing
"""
Created on Fri June 9 9:00:00 2023

@author: Rachael Fisher 

<<<<<<< Updated upstream
This script is used to crop within lens and find average fluorescence, stats for correlation
=======
This script is used to crop within lens and find average fluorescence and compare with Ephys data, correlation and cross correlation metrics
>>>>>>> Stashed changes
"""
import miniscope_ephys
import misc_functions
import numpy as np
from pylab import *
from scipy.signal import butter, freqz, filtfilt, firwin, bode
import matplotlib.pyplot as plt

#load data
lineNum = 36
channel ='PFCEEGvsCBEEG'

obj = miniscope_ephys.miniscopeEphys(lineNum)

obj.importEphysData()
obj.importNeuralynxEvents(analogSignalImported=True)
obj.syncNeuralynxMiniscopeTimestamps()
obj.findEphysIdxOfTTLEvents(CaEvents=False)


# for loading and cropping all calcium videos 
numMovies = int(np.ceil(len(obj.timeStamps)/1000)) # The total number of calcium movie files

for i in range(numMovies):
    obj.importCaMovies(os.path.join(obj.experiment['calcium imaging directory'], 'Miniscope', str(i) + '.avi'))
    obj.preprocessCaMovies(saveMovie=True, crop=True, cropGUI=False, square=square)

#if videos have already been analyzed
meanFluorescence_36 = np.load('/home/lab/Dropbox (Partners HealthCare)/miniscope_analysis/experimental_data/miniscope_data/propofol/R220817B/2022_11_28/14_25_30/Miniscope/meanFluorescence_36.npz')

fdataM = misc_functions.filterData(meanFluorescence_36['meanFluorescence'], n=2, cut=[2,4], ftype='butter', btype='bandpass', fs=obj.experiment['frameRate'])

#EEG DATA
obj.artifactRemoval(channel = channel, VThreshold=500) # VThreshold will change based on exp
obj.filterEphys(channel = channel, n=2, cut=[2,4],ftype='butter',inline=False)

#normalize...
normalizedM = fdataM / np.max(fdataM)
normalizedEEG = obj.fdata[0].data / np.max(obj.fdata[0].data)

#run the find miniscope movies to analyze script to get start and end values?

Mini_AOI = fdataM[start:end]
filteredEphys = obj.fdata[0].data[obj.ephysIdxAllTTLEvents[start:end]]  #prints array of filtered data
timestamps = obj.tEphys[channel][obj.ephysIdxAllTTLEvents]


#pick time regions of interest, sleep, dex ect
xcorr = correlate(fdataM[116300:125900], obj.fdata[0].data[obj.ephysIdxAllTTLEvents][116300:125900])

plt.figure()
plt.plot(scipy.signal.correlate(Mini_AOI, filteredEphys, mode='full', method='auto'))


____________________________________________________________________________________________________________________________________________________________________________________
#for if npz file not created yet
obj.computeProjections(time = True)
unfilteredCalcium = obj.projections["oneDim"]

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