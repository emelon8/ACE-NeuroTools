#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Oct 18 17:21:47 2023

@author: Luke Richards
"""

import miniscope_ephys
import misc_functions
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import correlate, correlation_lags


#%% configurable parameters
deepAnalysis = True
lineNum = 97  # 37, 38, 46, 47, 90, 92, 97, 101
channel = 'PFCLFPvsCBEEG'
meanFluorescenceFilePath = '/Users/lukerichards/Desktop/Correlation Project/npzFiles/meanFluorescence_'+ str(lineNum)+ '.npz'


#%% Load experiment 
obj = miniscope_ephys.miniscopeEphys(lineNum) 
fr = obj.experiment['frameRate']
obj.importEphysData(channels=channel)
obj.importNeuralynxEvents()
obj.syncNeuralynxMiniscopeTimestamps(channel=channel)
obj.findEphysIdxOfTTLEvents(channel=channel, CaEvents=False)
meanFluorescence = np.load(meanFluorescenceFilePath)

#%% Filter function
# miniscope = meanFluorescence['meanFluorescence']
# Returns the filtered flourescence and eeg data

def filterData(cut):
    # 'cut' is the range that will not be filtered out.

    # Filter the flourescence data via the misc_functions filter method
    filteredMeanFluorscence = misc_functions.filterData(meanFluorescence['meanFluorescence'], n=2, cut=cut, ftype='butter', btype='bandpass', fs=fr)
    
    # Filter the EEG data via object method call; this is saved in the object
    obj.filterEphys(channel=channel, n=2, cut=cut, ftype='butter', inline=False)
    return filteredMeanFluorscence, obj.fdata[0].data[obj.ephysIdxAllTTLEvents] # this second object is the filtered EEG data

#%% slice function
def processArrays(arr1, arr2, fr, interval_length=4, shift_length=0.5):
    # interval_length is the time interval in seconds.  It's the length of the window
    # shift_length is how large the window shifts 
    result = []
    timestamps = []
    lags = []
    sample_interval = int(interval_length * fr)  # Number of samples in a 4-second interval
    shift_samples = int(shift_length * fr)  # Number of samples to shift


    # Sliding window logic below:
    i = 0
    while i + sample_interval <= min(len(arr1), len(arr2)):
        miniscopeSlice = arr1[i:i + sample_interval]
        ephysSlice = arr2[i:i + sample_interval]
        
        interval_arr1 = miniscopeSlice/ np.std(miniscopeSlice)
        interval_arr2 = ephysSlice/ np.std(ephysSlice)
                
        
        # Calculate the max cross-correlation
        nxcorr = correlate(interval_arr1, interval_arr2) / interval_arr1.size
        maxXC = np.max(nxcorr)
        
        # Find the lag associated with the max cross-correlation
        nxcorrLags = correlation_lags(interval_arr1.size, interval_arr2.size) / fr
        nlag = nxcorrLags[np.argmax(nxcorr)]
        
        # Append results
        result = np.append(result, maxXC)
        lags = np.append(lags, nlag)
        timestamp = obj.tEphys[channel][obj.ephysIdxAllTTLEvents][i]
        timestamps = np.append(timestamps, timestamp)
        i += shift_samples

    return np.array(result), np.array(timestamps), np.array(lags)





#%% print results method
def printResults(filteredMeanFluorscence, filteredEEG, lagGraph=False):
    test, timestamps, lags = processArrays(filteredMeanFluorscence, filteredEEG, fr)
    plt.figure(num = 14)
    plt.plot(timestamps, test)
    plt.title('max cross correlation values for 4 second time intervals, experiment '+ str(lineNum)+ ' '+ obj.experiment['systemic drug'])
    plt.ylabel('normalized cross correlation value')
    plt.xlabel('time (s)'),
    
    # Lag graph
    if lagGraph:
        plt.plot(timestamps, lags)
        plt.title("Lag associated with highest X-Correllation over time")
        plt.xlabel('time (s)')
        plt.ylabel('lag')

#%% Average Correlations
def printMean(values):
    print(f"Cross-Correlation mean: " + str(values.mean()))


#%% Method to find highest cross correlation mean across different frequency ranges.  Only called if deepAnalysis is True
def findIdealFrequencyRange():
    meanMaxXC = []
    for i in range(0,6):
        filterStart = i*0.5  + 0.01  # lowest frequency.  can't be zero
        filterEnd = i*0.5 + 1     # highest frequency
        filteredMeanFluorscence = filterData([filterStart, filterEnd])
        intervalLength = 2 # in seconds
        intervalShift = intervalLength / 4 # in seconds
        test, timestamps, lags = processArrays(filteredMeanFluorscence, obj.fdata[0].data[obj.ephysIdxAllTTLEvents], fr, interval_length=intervalLength, shift_length=intervalShift)
        meanMaxXC.append(test.mean())
        
    # Find the maximum value in meanMaxXC and its corresponding index
    maxXC = max(meanMaxXC)
    maxIndex = meanMaxXC.index(maxXC)
    
    # Get the corresponding frequency range
    idealFrequencyRange = [maxIndex*0.5 + 0.01, maxIndex*0.5 + 1]
    
    # Print the results
    print(f"The greatest meanMaxXC value is {maxXC:.2f}")
    print(f"The corresponding frequency range is {idealFrequencyRange[0]:.2f} Hz to {idealFrequencyRange[1]:.2f} Hz")
    
    return maxXC, idealFrequencyRange



#%%
def runSimpleAnalysis():
    filteredMeanFluorscence, filteredEEG = filterData([1.4,2.4])
    printResults(filteredMeanFluorscence, filteredEEG)
        
def runDeepAnalysis():
    _, idealFrequencyRange = findIdealFrequencyRange()
    filteredMeanFluorscence, filteredEEG = filterData(idealFrequencyRange)
    printResults(filteredMeanFluorscence, filteredEEG)
#%%
if deepAnalysis==True:
    print("\nRunning deep analysis")
    runDeepAnalysis()
    
else:
    print("\nRunning simple analysis")
    runSimpleAnalysis()




#%%
    # for i in range(0,6):
    #     filterStart = i*0.5  + 0.01  # lowest frequency.  can't be zero
    #     filterEnd = i*0.5 + 1     # highest frequency
    #     filteredMeanFluorscence = filter_data([filterStart, filterEnd])
    #     intervalLength = 2 # in seconds
    #     intervalShift = intervalLength / 4 # in seconds
    #     test, timestamps, lags = process_arrays(filteredMeanFluorscence, obj.fdata[0].data[obj.ephysIdxAllTTLEvents], fr, interval_length=intervalLength, shift_length=intervalShift)
    #     print("Interval Length: " + str(intervalLength))
    #     print("Interval Shift: " + str(intervalShift))
    #     print("Filter Start: " + str(filterStart) + " Filter End: " + str(filterEnd))
    #     printMean(test)
    #     print("\n")
