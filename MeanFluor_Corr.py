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
import numpy as np
from pylab import *
from scipy import signal
import matplotlib.pyplot as plt

#load data
lineNum = 41
channel ='PFCEEGvsCBEEG'

obj = miniscope_ephys.miniscopeEphys(lineNum=lineNum)
obj.importCaMovies(obj.experiment['calcium imaging directory']+'/Miniscope/0.avi')

#importing data and synching timestamps
obj.importEphysData(channels=channel)
obj.importNeuralynxEvents(analogSignalImported=True)
obj.syncNeuralynxMiniscopeTimestamps(channel=channel)

#ephys timestamps nearest to TTL events
obj.findEphysIdxOfTTLEvents(channel=channel, CaEvents=False)

#filters EEG thru FIR filter, inline = False puts data into fdata[index].data

obj.filterEphys(channel=channel, inline = False)
filteredEphys = obj.fdata[0].data #prints array of filtered data

#normalize data 
#thinking through best technique to do this, research more
zscore = filteredEphys - np.mean(filteredEphys) / np.std(filteredEphys)
normalized1 = filteredEphys/np.max(filteredEphys) 
normalized2 = (filteredEphys - np.min(filteredEphys))/ np.ptp(filteredEphys) # zero to one


#get timesstamps of data
timestamps = obj.ephys[channel][obj.ephysIdxAllTTLEvents]

#crop and preprocess 
#Update preprocess and _crop soon to be able to get rid of these new functions and just have an argument called colname
#cropSquareProcessing(self, saveMovie=False, crop=False, cropGUI=False, denoise=False, detrend=False, dFoverF=False) #defaults
obj.cropSquarePreprocessing(crop = True, cropGUI = True)

#gives array of values, 1000x608x608 if not cropped yet, smaller if changed in crop GUI
#collapsed is the 1d array that summerizes the 3d matrix from movie
#averages across x and y to give a value for each time interval (np.shape(collapsed) should be the time axis)
values = obj.movie 
np.shape(values)
collapsed = values.mean(axis=(1,2))
np.shape(collapsed)

#plot of collapsed array
frame = np.arange(0,1000)
plt.plot(times, collapsed)
xlabel('frame')                                    
ylabel('Average Fluorescence')
filteredMini = collapsed.filterEphys(channel=channel)
