#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Jan  1 18:38:43 2025

@author: lukerichards
"""

import xarray as xr
from xrscipy.signal.spectral import coherogram
from classes import miniscope_ephys
import numpy as np
import matplotlib.pyplot as plt


lineNums =  [35, 37, 38, 83, 90, 92, 35, 46, 47, 101, 97, 64, 88 , 104, 105, 107, 108] #35, 37, 38, 83, 90, 92, 35, 46, 47, 101, 97, 64, 88 , 104, 105, 107, 108
plotMagnitude = False
plotCoherence = False

# uploaded: 97, 37, 46, 47

data = {
    "sleep": [37,38,83,90,92,35],
    "dexmedetomidine": [46,47,101,97,64,88],
    "isoflurane": [104,105,107,108]
}

# Create a reverse mapping from numbers to drug types
number_to_drug = {num: drug for drug, numbers in data.items() for num in numbers}


channel = 'PFCLFPvsCBEEG'

def lineNum_to_chart(lineNum, drug, meanFluorescenceFilePath):
    #%% Load experiment 
    obj = miniscope_ephys.miniscopeEphys(lineNum) 
    fr = obj.experiment['frameRate']
    obj.importEphysData(channels=channel)
    obj.importNeuralynxEvents()
    obj.syncNeuralynxMiniscopeTimestamps(channel=channel)
    obj.findEphysIdxOfTTLEvents(channel=channel, CaEvents=False)
    meanFluorescence = np.load(meanFluorescenceFilePath)
    obj.filterEphys(channel=channel, n=2, cut=[0.001,20], ftype='butter', inline=False)
    
    
    
    #%% Find highest correaltion frequency range via a cross-spectral density
    
    # EEG and calcium signals
    eeg_signal = obj.fdata[0].data[obj.ephysIdxAllTTLEvents] # EEG signal
    calcium_signal = meanFluorescence['meanFluorescence']  # Calcium signal
    
    eeg_data = xr.DataArray(eeg_signal, dims=["time"], coords={"time": np.arange(len(eeg_signal)) / fr})
    calcium_data = xr.DataArray(calcium_signal, dims=["time"], coords={"time": np.arange(len(calcium_signal)) / fr})


    # Define the spectrogram parameters
    windowLength = 30  # in seconds
    windowStep = 3  # in seconds
    fs = fr  # Sampling frequency (frame rate)
    
    # Compute the overlap ratio
    overlap_ratio = 1 - (windowStep / windowLength)
    
    # Ensure EEG and calcium signals are compatible with the new settings
    eeg_data = xr.DataArray(eeg_signal, dims=["time"], coords={"time": np.arange(len(eeg_signal)) / fr})
    calcium_data = xr.DataArray(calcium_signal, dims=["time"], coords={"time": np.arange(len(calcium_signal)) / fr})
    
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
    
    # Plot the coherogram
    plt.figure(figsize=(10, 6))
    
    # Use imshow for plotting the coherogram
    coh_magnitude = abs(coh) ** 2  # Coherence magnitude squared
    im = coh_magnitude.plot.imshow(cmap="viridis", robust=True)  # Automatically handles the colorbar
    
    # Update the color bar label
    colorbar = im.colorbar
    colorbar.set_label("Coherence", fontsize=12)
    
    plt.title(f"Coherogram {drug} line {lineNum}")
    plt.xlabel("Time (s)")
    plt.ylabel("Frequency (Hz)")
    
    plt.show()




    
    
for lineNum in lineNums:
    drug = number_to_drug.get(lineNum)
    meanFluorescenceFilePath = f'/Users/lukerichards/Desktop/Correlation Project/npzFiles/{drug}/meanFluorescence_{str(lineNum)}.npz'
    lineNum_to_chart(lineNum, drug, meanFluorescenceFilePath)







