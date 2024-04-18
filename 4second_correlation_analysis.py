#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Oct 18 17:21:47 2023

@author: lab
"""

import miniscope_ephys
import misc_functions
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import correlate, correlation_lags, coherence
from scipy.stats import pearsonr

lineNum = 97
channel = 'PFCLFPvsCBEEG'

#%% slice function
def process_arrays(arr1, arr2, fr):
    result = []
    timestamps = []
    lags = []
    interval_length = 4  # Time interval in seconds
    shift_length = 0.5  # Shift length in seconds
    sample_interval = int(interval_length * fr)  # Number of samples in a 4-second interval
    shift_samples = int(shift_length * fr)  # Number of samples to shift

    i = 0
    while i + sample_interval <= min(len(arr1), len(arr2)):
        miniscopeSlice = arr1[i:i + sample_interval]
        ephysSlice = arr2[i:i + sample_interval]
        
        interval_arr1 = miniscopeSlice/ np.std(miniscopeSlice)
        interval_arr2 = ephysSlice/ np.std(ephysSlice)
        
        # xc calc
        nxcorr = correlate(interval_arr1, interval_arr2) / interval_arr1.size
        maxXC = np.max(nxcorr)
        nxcorrLags = correlation_lags(interval_arr1.size, interval_arr2.size) / fr
        nlag = nxcorrLags[np.argmax(nxcorr)]
        result = np.append(result, maxXC)
        lags = np.append(lags, nlag)
        timestamp = obj.tEphys[channel][obj.ephysIdxAllTTLEvents][i]
        timestamps = np.append(timestamps, timestamp)
        i += shift_samples

    return np.array(result), np.array(timestamps), np.array(nlag)

#%% Load experiment 
obj = miniscope_ephys.miniscopeEphys(lineNum)
fr = obj.experiment['frameRate']
obj.importEphysData(channels=[channel, 'PFCEEGvsCBEEG'])
obj.importNeuralynxEvents(analogSignalImported=True)
obj.syncNeuralynxMiniscopeTimestamps(channel=channel)
obj.findEphysIdxOfTTLEvents(channel=channel, CaEvents=False)
meanFluorescence = np.load('/home/lab/Desktop/Correlation Project/npzFiles/meanFluorescence_'+ str(lineNum)+ '.npz')


#%% downsample and filter
miniscope = meanFluorescence['meanFluorescence']
times = obj.tEphys[channel][obj.ephysIdxAllTTLEvents]

fdataM = misc_functions.filterData(meanFluorescence['meanFluorescence'], n=2, cut=[1,3], ftype='butter', btype='bandpass', fs=fr)
obj.filterEphys(channel=channel, n=2, cut=[1,3], ftype='butter', inline=False)

#%% results
test, timestamps, lags = process_arrays(fdataM, obj.fdata[0].data[obj.ephysIdxAllTTLEvents], fr)
plt.figure(num = 14)
plt.plot(timestamps, test)
plt.title('max cross correlation values for 4 second time intervals, experiment '+ str(lineNum)+ ' '+ obj.experiment['systemic drug'])
plt.ylabel('normalized cross correlation value')
plt.xlabel('time (s)')
