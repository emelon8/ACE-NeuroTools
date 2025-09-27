#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Jan  1 18:38:43 2025

@author: lukerichards
"""

import xarray as xr
from xrscipy.signal.spectral import coherogram
from src.classes import miniscope_ephys
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
    

    # Define the spectrogram parameters
    windowLength = 5  # in seconds
    windowStep = 2.5  # in seconds
    
    # Compute the overlap ratio
    overlap_ratio = 1 - (windowStep / windowLength)
    
    # Debug: EEG and calcium signal lengths and sample frequencies
    print(f"EEG signal length: {len(eeg_signal)}")
    print(f"Calcium signal length: {len(calcium_signal)}")
    print(f"Sampling frequency (fr): {fr}")
    
    # Check time coordinate values after conversion to minutes
    eeg_times = np.arange(len(eeg_signal)) / (fr * 60)
    calcium_times = np.arange(len(calcium_signal)) / (fr * 60)
    
    print(f"First 10 EEG time coordinates (minutes): {eeg_times[:10]}")
    print(f"First 10 Calcium time coordinates (minutes): {calcium_times[:10]}")
    
    # Create xarray DataArrays for EEG and Calcium signals
    eeg_data = xr.DataArray(
        eeg_signal,
        dims=["time"],
        coords={"time": eeg_times}
    )
    calcium_data = xr.DataArray(
        calcium_signal,
        dims=["time"],
        coords={"time": calcium_times}
    )
    
    # Debug: Verify the time coordinates in the created DataArrays
    print(f"EEG DataArray time coordinates (first 10): {eeg_data['time'].values[:10]}")
    print(f"Calcium DataArray time coordinates (first 10): {calcium_data['time'].values[:10]}")
    
    # Compute the coherogram
    coh = coherogram(
        eeg_data,
        calcium_data,
        fs=fr,  
        seglen=windowLength,  
        overlap_ratio=overlap_ratio,  
        nrolling=8,  
        window="hann"  
    )
    
    # Debug: Check coherogram time coordinates
    print(f"Coherogram time coordinates (first 10): {coh['time'].values[:10]}")
    
    # Plot the coherogram
    plt.figure(figsize=(10, 6))
    
    coh_magnitude = abs(coh) ** 2  
    im = coh_magnitude.plot.imshow(
        cmap="viridis", 
        robust=False,  
        vmin=0, vmax=0.7  
    )
    
    # Debug: Ensure x-axis label matches intended units
    print(f"X-axis label: {plt.gca().get_xlabel()}")
    
    # Update the color bar label
    colorbar = im.colorbar
    colorbar.set_label("Coherence", fontsize=12)
    
    # Add title and axis labels
    plt.title(f"Coherogram {drug} line {lineNum}")
    plt.xlabel("Time (minutes)")
    plt.ylabel("Frequency (Hz)")
    
    plt.show()









    
    
for lineNum in lineNums:
    drug = number_to_drug.get(lineNum)
    meanFluorescenceFilePath = f'/Users/lukerichards/Desktop/Correlation Project/npzFiles/{drug}/meanFluorescence_{str(lineNum)}.npz'
    lineNum_to_chart(lineNum, drug, meanFluorescenceFilePath)







