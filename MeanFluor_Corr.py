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
from scipy.signal import butter, freqz, filtfilt, firwin, bode
import matplotlib.pyplot as plt

#load data
lineNum = 41
channel ='PFCEEGvsCBEEG'

obj = miniscope_ephys.miniscopeEphys(lineNum)
# for all calcium videos 
obj.findMovieFilePaths()
obj.importCaMovies(obj.movieFilePaths[0:5])
#___________________________________________________________________________________________
#OR (once i add something to get number of videos)

#moviePath = '../../experimental_data/miniscope_data/sleep/R220817B/2022_11_25/14_04_09/Miniscope/'
#movieFilenameAfterNum = '_cropped.avi'
#movieNums = np.arange(5)
#movieList = []
#for k in movieNums:
#    movieList.append(os.path.join(moviePath, str(k) + movieFilenameAfterNum))

#obj.importCaMovies(movieList)
#___________________________________________________________________________________________
#just one video
#obj.importCaMovies(obj.experiment['calcium imaging directory']+'/Miniscope/0.avi')
#___________________________________________________________________________________________
#slow... 6 min for 5 videos... efficiency improvements?
obj.preprocessCaMovies(crop = True, square = True, cropGUI = False)
obj.computeProjections(time = True)

#filter the calcium data 
obj.filterMiniscope(inline = False)
filteredCalcium = obj.fdata[0].data

zscoreCa = (filteredCalcium - np.mean(filteredCalcium)) / np.std(filteredCalcium)
normalizedCa1 = filteredCalcium/np.max(filteredCalcium) 
normalizedCa2 = (filteredCalcium - np.min(filteredCalcium))/ np.ptp(filteredCalcium) # zero to one

#importing data and synching timestamps
obj.importEphysData(channels=channel)
obj.importNeuralynxEvents(analogSignalImported=True)
obj.syncNeuralynxMiniscopeTimestamps(channel=channel)

#ephys timestamps nearest to TTL events
obj.findEphysIdxOfTTLEvents(channel=channel, CaEvents=False)

#filters EEG thru butter filter, inline = False puts data into fdata[index].data
obj.filterEphys(n=2, cut=[10,15], channel=channel, ftype='butter', btype='bandpass', inline= False)
filteredEphys = obj.fdata[0].data #prints array of filtered data
unfilteredEphys = obj.ephys[channel]

#normalize EEG data 
#thinking through best technique to do this, research more
zscore = (filteredEphys - np.mean(filteredEphys)) / np.std(filteredEphys)
normalized1 = filteredEphys/np.max(filteredEphys) 
normalized2 = (filteredEphys - np.min(filteredEphys))/ np.ptp(filteredEphys) # zero to one

#get timesstamps of EEG data
timestamps = obj.tEphys[channel][obj.ephysIdxAllTTLEvents[0:len(filteredCalcium)]]

#plot of collapsed array
plt.plot(timestamps, zscoreCa)
plt.plot(timestamps, zscore[0:1000])
plt.show()
xlabel('frame')                                    
ylabel('Average Fluorescence')

#_______________________________________________________________________________________________________________________________________________________________________________________________________________________

import miniscope_ephys
import numpy as np
from pylab import *
from scipy.signal import butter, freqz, filtfilt, firwin, bode
import matplotlib.pyplot as plt

#load data
lineNum = 41
channel ='PFCEEGvsCBEEG'

obj = miniscope_ephys.miniscopeEphys(lineNum)
# for all calcium videos 
obj.findMovieFilePaths()
obj.importCaMovies(obj.movieFilePaths[0:5])

obj.preprocessCaMovies(crop = True, square = True, cropGUI = False)
obj.computeProjections(time = True)

unfilteredCalcium = obj.projections["oneDim"]

obj.filterMiniscope(inline = False)
filteredCalcium = obj.fdata[0].data

zscoreCa = (filteredCalcium - np.mean(filteredCalcium)) / np.std(filteredCalcium)
normalizedCa1 = filteredCalcium/np.max(filteredCalcium) 
normalizedCa2 = (filteredCalcium - np.min(filteredCalcium))/ np.ptp(filteredCalcium) # zero to one

obj.importEphysData(channels=channel)
obj.importNeuralynxEvents(analogSignalImported=True)
obj.syncNeuralynxMiniscopeTimestamps(channel=channel)

obj.findEphysIdxOfTTLEvents(channel=channel, CaEvents=False)

obj.filterEphys(n=2, cut=[10,15], channel=channel, ftype='butter', btype='bandpass', inline= False)
filteredEphys = obj.fdata[1].data[obj.ephysIdxAllTTLEvents[0:len(filteredCalcium)]] #prints array of filtered data
unfilteredEphys = obj.ephys[channel][obj.ephysIdxAllTTLEvents[0:len(filteredCalcium)]]

zscoreEphys = (filteredEphys - np.mean(filteredEphys)) / np.std(filteredEphys)
normalized1Ephys = filteredEphys/np.max(filteredEphys) 
normalized2Ephys = (filteredEphys - np.min(filteredEphys))/ np.ptp(filteredEphys) # zero to one

timestamps = obj.tEphys[channel][obj.ephysIdxAllTTLEvents[0:len(filteredCalcium)]]

plt.plot(timestamps, normalized1Ephys)
plt.plot(timestamps, normalizedCa1)
plt.show()