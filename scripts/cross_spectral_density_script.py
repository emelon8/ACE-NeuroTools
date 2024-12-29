#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Dec 26 21:01:12 2024

@author: lukerichards
"""

import miniscope_ephys
import misc_functions
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import correlate, correlation_lags, coherence, csd, welch
from scipy.stats import pearsonr

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
obj.filterEphys(channel=channel, n=2, cut=[0.001,20], ftype='butter', inline=False)



#%% Find highest correaltion frequency range via a cross-spectral density

# EEG and calcium signals
eeg_signal = obj.fdata[0].data[obj.ephysIdxAllTTLEvents] # EEG signal
calcium_signal = meanFluorescence['meanFluorescence']  # Calcium signal

# Cross-Spectral Density
f, Pxy = csd(eeg_signal, calcium_signal, fs=fr, nperseg=1024)

# Auto-spectral densities for normalization (optional)
_, Pxx = welch(eeg_signal, fs=fr, nperseg=1024)
_, Pyy = welch(calcium_signal, fs=fr, nperseg=1024)

# Magnitude of CSD (cross-power) and normalize
magnitude = np.abs(Pxy)
coherence = magnitude**2 / (Pxx * Pyy)  # Optional: Use coherence for correlation strength

# Find maximum cross-correlation magnitude and corresponding frequency
max_corr_freq = f[np.argmax(magnitude)]
max_corr_value = np.max(magnitude)

# Plot magnitude spectrum
plt.figure(figsize=(10, 6))
plt.plot(f, magnitude, label="CSD Magnitude")
plt.title("Cross-Spectral Density (CSD) Magnitude")
plt.xlabel("Frequency (Hz)")
plt.ylabel("Magnitude")
plt.axvline(max_corr_freq, color="r", linestyle="--", label=f"Max at {max_corr_freq:.2f} Hz")
plt.xlim(0, 4) 
plt.legend()
plt.grid()
plt.show()

# Print max values
print(f"Maximum CSD magnitude: {max_corr_value:.3f} at {max_corr_freq:.2f} Hz")