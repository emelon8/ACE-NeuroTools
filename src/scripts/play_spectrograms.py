#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Jan  2 19:53:41 2025

@author: lukerichards
"""

from src.classes import miniscope_ephys

import matplotlib.pyplot as plt  # Ensure Matplotlib is imported if not already
import numpy as np
import xarray as xr
from xrscipy.signal.spectral import coherogram
from src.classes import miniscope_ephys

#%% metadata

lineNums = [35, 37, 38, 83, 90, 92, 46, 47, 101, 97, 64, 88, 104, 105, 107, 108]
lineNum = 64
channel = 'PFCLFPvsCBEEG'

data = {
    "sleep": [37, 38, 83, 90, 92, 35],
    "dexmedetomidine": [46, 47, 101, 97, 64, 88],
    "isoflurane": [104, 105, 107, 108]
}

# Create a reverse mapping from numbers to drug types
number_to_drug = {num: drug for drug, numbers in data.items() for num in numbers}

# Time range mapping for each line number as pairs of numbers
selections = {
    35: [10, 51],
    37: [58, 101],
    38: [32, 78],
    83: [10, 20],
    90: [21, 103],
    92: [120, 100],
    46: [5, 30],
    47: [5, 34],
    101: [10, 75],
    97: [10, 60],
    64: [20, 40],
    88: [10, 50],
    104: [5, 60],
    105: [30, 60],
    107: [5, 100],
    108: [5, 60],
}

#%% Load experiment 
def loadExperiment(line, meanFluorescenceFilePath):
    obj = miniscope_ephys.miniscopeEphys(lineNum) 
    fr = obj.experiment['frameRate']
    obj.importEphysData(channels=channel)
    obj.importNeuralynxEvents()
    obj.syncNeuralynxMiniscopeTimestamps(channel=channel)
    obj.findEphysIdxOfTTLEvents(channel=channel, CaEvents=False)
    meanFluorescence = np.load(meanFluorescenceFilePath)
    obj.filterEphys(channel=channel, n=2, cut=[0.001,20], ftype='butter', inline=False)
    return obj, fr, meanFluorescence
    

#%% Plot lines
WIDTH = 0.4

def plotLinesAx(lineNum, ax):
    a = ax.axvline(x=selections[lineNum][0], color='red', linestyle='--', linewidth=WIDTH)
    ax.axvline(x=selections[lineNum][0] + 0.33, color='red', linestyle='--', linewidth=WIDTH)
    
    b = ax.axvline(x=selections[lineNum][1], color='orange', linestyle='--', linewidth=WIDTH)
    ax.axvline(x=selections[lineNum][1] + 0.33, color='orange', linestyle='--', linewidth=WIDTH)
    
    ax.legend([a, b], ['Control', 'Treatment'])

def plotLinesPlt(lineNum, plt):
    plt.axvline(x=selections[lineNum][0], color='red', linestyle='--', linewidth=WIDTH)
    plt.axvline(x=selections[lineNum][0] + 0.33, color='red', linestyle='--', linewidth=WIDTH)
    
    plt.axvline(x=selections[lineNum][1], color='orange', linestyle='--', linewidth=WIDTH)
    plt.axvline(x=selections[lineNum][1] + 0.33, color='orange', linestyle='--', linewidth=WIDTH)
    plt.legend()

#%% Plot Spectrogram

def plotSpectrogram(line, obj, fr):
    
    
    h, ax = obj.computeSpectrogram(windowLength=5, windowStep=5, freqLims=[0.01, 20])
    plt.figure(figsize=(10,6))
    
    # Add title with line number and associated drug
    drug = number_to_drug.get(line, "Unknown")
    ax.set_title(f"Line Number: {line} | Drug: {drug}", fontsize=9)
    
    # Plot red lines using the mapping
    plotLinesAx(line, ax)
    

    plt.tight_layout()
    plt.show()  # Display the graph
    
    
    

    
    
#%% Plot Coherogram
    
def plotCoherogram(lineNum, drug, meanFluorescenceFilePath, obj, fr): 
    
    # EEG and calcium signals
    eeg_signal = obj.fdata[0].data[obj.ephysIdxAllTTLEvents] # EEG signal
    calcium_signal = meanFluorescence['meanFluorescence']  # Calcium signal
    

    # Define the spectrogram parameters
    windowLength = 5  # in seconds
    windowStep = 2.5  # in seconds
    
    # Compute the overlap ratio
    overlap_ratio = 1 - (windowStep / windowLength)
    
    # Convert time coordinates to minutes
    eeg_data = xr.DataArray(
        eeg_signal,
        dims=["time"],
        coords={"time": np.arange(len(eeg_signal)) / (fr * 60)}  # Convert to minutes
    )
    calcium_data = xr.DataArray(
        calcium_signal,
        dims=["time"],
        coords={"time": np.arange(len(calcium_signal)) / (fr * 60)}  # Convert to minutes
    )
    
    # Compute the coherogram
    coh = coherogram(
        eeg_data,
        calcium_data,
        fs=fr,  # Sampling frequency
        seglen=windowLength,  # Match spectrogram's window length
        overlap_ratio=overlap_ratio,  # Calculated overlap ratio
        nrolling=8,  # Rolling average over 8 FFT windows
        window="hann"  # Hann window
    )
    
    coh["time"] = coh["time"] / 60
    
    # Plot the coherogram
    plt.figure(figsize=(10, 6))
    
    # Use imshow for plotting the coherogram
    coh_magnitude = abs(coh) ** 2  # Coherence magnitude squared
    im = coh_magnitude.plot.imshow(
        cmap="viridis", 
        robust=False,  # Disable automatic color scaling
        vmin=0, vmax=0.7  # Fix the color range to [0, 0.7]
    )
    
    # Update the color bar label
    colorbar = im.colorbar
    colorbar.set_label("Coherence", fontsize=12)
    
    # Add title and axis labels
    plt.title(f"Coherogram {drug} line {lineNum}")
    plt.xlabel("Time (minutes)")
    plt.ylabel("Frequency (Hz)")
    
    plt.legend()

    plotLinesPlt(lineNum, plt)

    
    plt.show()
    
#%% main

for lineNum in lineNums:
    drug = number_to_drug.get(lineNum)
    meanFluorescenceFilePath = f'/Users/lukerichards/Desktop/Correlation Project/npzFiles/{drug}/meanFluorescence_{str(lineNum)}.npz'
    obj, fr, meanFluorescence = loadExperiment(lineNum, meanFluorescenceFilePath)
    plotSpectrogram(lineNum, obj, fr)
    plotCoherogram(lineNum, drug, meanFluorescenceFilePath, obj, fr)
    


    

