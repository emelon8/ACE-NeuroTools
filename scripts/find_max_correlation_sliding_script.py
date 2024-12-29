#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Dec 27 13:09:20 2024

@author: lukerichards
"""




import sys
from pathlib import Path

# Add the project root to sys.path for imports to work
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))


import os
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import correlate, correlation_lags
from classes import miniscope_ephys
import misc_functions
import statistics
#%%  Configurable Parameters

LINE_NUM = 97  # 37, 38, 46, 47, 90, 92, 97, 101
CHANNEL = 'PFCLFPvsCBEEG'
MEAN_FLUORESCENCE_FILE = f'/Users/lukerichards/Desktop/Correlation Project/npzFiles/meanFluorescence_{LINE_NUM}.npz'
RUN_DEEP_ANALYSIS = True

#%% Load Data Method
def loadData(lineNum, channel, fluorescenceFile):
    """
    Load data required for analysis.

    Args:
        lineNum (int): Line number identifying the experiment.
        channel (str): Ephys channel to be analyzed.
        fluorescenceFile (str): Path to the mean fluorescence .npz file.

    Returns:
        tuple: A miniscopeEphys object with loaded data and a NumPy array of mean fluorescence.
    """
    obj = miniscope_ephys.miniscopeEphys(lineNum)
    obj.importEphysData(channels=channel)
    obj.importNeuralynxEvents()
    obj.syncNeuralynxMiniscopeTimestamps(channel=channel)
    obj.findEphysIdxOfTTLEvents(channel=channel, CaEvents=False)
    meanFluorescence = np.load(fluorescenceFile)
    return obj, meanFluorescence

#%% Filter Data Method

def filterFrequency(obj, meanFluorescence, frameRate, channel, cut):
    """
    Apply bandpass filtering to fluorescence and ephys data.

    Args:
        obj (miniscopeEphys): Object containing ephys and event data.
        meanFluorescence (np.array): Array of mean fluorescence data.
        frameRate (float): Frame rate of the experiment.
        channel (str): Ephys channel to be analyzed.
        cut (list): Frequency range for bandpass filtering.

    Returns:
        tuple: Filtered fluorescence data and filtered ephys data aligned with TTL events.
    """
    filteredFluorescence = misc_functions.filterData(
        meanFluorescence['meanFluorescence'], n=2, cut=cut, ftype='butter', btype='bandpass', fs=frameRate
    )
    obj.filterEphys(channel=channel, n=2, cut=cut, ftype='butter', inline=True) 
    # inline=True stores the filtered data in a new place instead of modifying it in place.  this is crucial for finding the ideal range as filters many times
    
    return filteredFluorescence, obj.ephys[channel][obj.ephysIdxAllTTLEvents]


#%% Process Arrays Method

def processArrays(arr1, arr2, frameRate, intervalLength=2, shiftLength=0.5):
    """
    Perform cross-correlation with sliding windows on two input arrays.

    Args:
        arr1 (np.array): First time-series array.
        arr2 (np.array): Second time-series array.
        frameRate (float): Frame rate of the experiment.
        intervalLength (float): Length of sliding window in seconds.
        shiftLength (float): Shift interval for sliding window in seconds.

    Returns:
        tuple: Arrays of cross-correlation xCorrResults, timestamps, and corresponding lags.
    """
    xCorrResults, timestamps, lags = [], [], []
    sampleInterval = int(intervalLength * frameRate)
    shiftSamples = int(shiftLength * frameRate)
    
   

    for i in range(0, min(len(arr1), len(arr2)) - sampleInterval, shiftSamples):
        window1 = arr1[i:i + sampleInterval]
        window2 = arr2[i:i + sampleInterval]

        # Normalize each window by its mean, standard deviation, and length
        window1 = (window1 - np.mean(window1)) / (np.std(window1)*len(window1))
        window2 = (window2 - np.mean(window2)) / np.std(window2)

        # Compute the cross-correlation and normalize by the length
        nxcorr = correlate(window1, window2, mode='full')
        
        
        # Calculate the lags corresponding to the cross-correlation
        lagsCorr = correlation_lags(len(window1), len(window2), mode='full') / frameRate

        # Store the maximum cross-correlation and corresponding lag
        xCorrResults.append(np.max(nxcorr))
        lags.append(lagsCorr[np.argmax(nxcorr)])
        timestamps.append(i / frameRate)

    return np.array(xCorrResults), np.array(timestamps), np.array(lags)


#%% Find Ideal Frequency Range Method

def findIdealFrequencyRange(obj, meanFluorescence, frameRate, channel):
    """
    Identify the frequency range with the highest cross-correlation.

    Args:
        obj (miniscopeEphys): Object containing ephys and event data.
        meanFluorescence (np.array): Array of mean fluorescence data.
        frameRate (float): Frame rate of the experiment.
        channel (str): Ephys channel to be analyzed.

    Returns:
        tuple: Maximum cross-correlation value and the corresponding frequency range.
    """
    
    # Reload Data:
    
    FREQUENCY_BOTTOM_BOUND = 0.01 # cannot be zero
    FREQUENCY_TOP_BOUND = 3.02
    STEP = 0.1
    
    xCorrResultsMeans = []
    for i in np.arange(FREQUENCY_BOTTOM_BOUND, FREQUENCY_TOP_BOUND - 1, STEP):
        filterStart = i  
        filterEnd = i + 1
        
        print(f"range: [{filterStart:.2f}, {filterEnd:.2f}]")
        
        # Reload the original data before filtering
        obj.importEphysData(channels=channel)
        
        # Filter and process
        filteredFluorescence, filteredEEG = filterFrequency(obj, meanFluorescence, frameRate, channel, [filterStart, filterEnd])
        xCorrResults, _, _ = processArrays(filteredFluorescence, filteredEEG, frameRate)
        
        # Append the mean xcorr values (over time) to a list
        meanCorrelation = np.mean(xCorrResults)
        print(f"Appending meanCorrelation: {meanCorrelation}")
        xCorrResultsMeans.append(meanCorrelation)
        print("\n")


    maxXC = max(xCorrResultsMeans)
    maxIndex = xCorrResultsMeans.index(maxXC)
    print(xCorrResultsMeans)
    idealFrequencyRange = [maxIndex * STEP + FREQUENCY_BOTTOM_BOUND, maxIndex * STEP + FREQUENCY_BOTTOM_BOUND + 1]
    
    

    print(f"The greatest meanMaxXC value is {maxXC:.2f}")
    print(f"The corresponding frequency range is {idealFrequencyRange[0]:.3f} Hz to {idealFrequencyRange[1]:.3f} Hz")
    return maxXC, idealFrequencyRange

#%% Simple Analysis Method
def simpleAnalysis(obj, meanFluorescence, frameRate, channel):
    """
    Perform an analysis of cross-correlation over a fixed frequency range.

    Args:
        obj (miniscopeEphys): Object containing ephys and event data.
        meanFluorescence (np.array): Array of mean fluorescence data.
        frameRate (float): Frame rate of the experiment.
        channel (str): Ephys channel to be analyzed.
    """
    
    FREQUENCY_BOTTOM_BOUND = 1.91 # cannot be zero
    FREQUENCY_TOP_BOUND = 2.91
    
    
    filteredFluorescence, filteredEEG = filterFrequency(obj, meanFluorescence, frameRate, channel, [FREQUENCY_BOTTOM_BOUND, FREQUENCY_TOP_BOUND])
    xCorrResults, timestamps, _ = processArrays(filteredFluorescence, filteredEEG, frameRate)
    
    
    
    # Plot results
    plt.plot(timestamps, xCorrResults)
    plt.title(f"Max XC values for 2 sec window, [{FREQUENCY_BOTTOM_BOUND}-{FREQUENCY_TOP_BOUND}] hz, Experiment {LINE_NUM} {obj.experiment['systemic drug']}")
    plt.xlabel("Time (s)")
    plt.ylabel("Normalized Cross-Correlation")
    mean_xcorr = np.mean(xCorrResults)
    plt.axhline(mean_xcorr, color='red', linestyle='--', label=f"Mean XC ({mean_xcorr:.4f})")
    plt.legend()
    plt.show()

#%% Deep Analysis Method

def deepAnalysis(obj, meanFluorescence, frameRate, channel):
    """
    Perform an analysis of cross-correlation over the ideal frequency range.

    Args:
        obj (miniscopeEphys): Object containing ephys and event data.
        meanFluorescence (np.array): Array of mean fluorescence data.
        frameRate (float): Frame rate of the experiment.
        channel (str): Ephys channel to be analyzed.
    """
    
    
    # Find ideal frequency range
    _, idealFrequencyRange = findIdealFrequencyRange(obj, meanFluorescence, frameRate, channel)
    
    # Filter according to that frequency
    filteredFluorescence, filteredEEG = filterFrequency(obj, meanFluorescence, frameRate, channel, idealFrequencyRange)
    
    # process arrays
    xCorrResults, timestamps, lags = processArrays(filteredFluorescence, filteredEEG, frameRate)
    
    
    # Plot results
    plt.plot(timestamps, xCorrResults, label="Max Cross-Correlation")
    # plt.plot(timestamps, lags, label="Lag at Max Correlation")
    plt.title(f"Max XC values for 4 sec window, {idealFrequencyRange[0]:.2f}-{idealFrequencyRange[1]:.2f} hz, Experiment {LINE_NUM} {obj.experiment['systemic drug']}")
    plt.xlabel("Time (s)")
    plt.ylabel("Value")
    mean_xcorr = np.mean(xCorrResults)
    plt.axhline(mean_xcorr, color='red', linestyle='--', label=f"Mean XC ({mean_xcorr:.3f})")
    plt.legend()
    plt.show()

#%% Main 
if __name__ == "__main__":
    """
    Main entry point for the analysis pipeline. Configures data loading and 
    executes either simple or deep analysis based on user preference.
    """
    obj, meanFluorescence = loadData(LINE_NUM, CHANNEL, MEAN_FLUORESCENCE_FILE)
    FRAME_RATE = obj.experiment['frameRate']
    

    if RUN_DEEP_ANALYSIS:
        print("\nRunning Deep Analysis")
        deepAnalysis(obj, meanFluorescence, FRAME_RATE, CHANNEL)
    else:
        print("\nRunning Simple Analysis")
        simpleAnalysis(obj, meanFluorescence, FRAME_RATE, CHANNEL)
