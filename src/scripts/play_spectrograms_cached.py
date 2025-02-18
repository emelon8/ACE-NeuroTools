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
from scipy.signal import correlate, correlation_lags
from scipy.signal import coherence
from src.classes import miniscope_ephys
import pandas as pd
from src import misc_functions


#%% metadata

lineNums = [35, 37, 38, 83, 90, 92, 46, 47, 101, 97, 64, 88, 104, 105, 107, 108]
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
WIDTH = 0.5

def plotLinesAx(lineNum, ax):
    a = ax.axvline(x=selections[lineNum][0], color='red', linestyle='--', linewidth=WIDTH)
    ax.axvline(x=selections[lineNum][0] + 0.33, color='red', linestyle='--', linewidth=WIDTH)
    
    b = ax.axvline(x=selections[lineNum][1], color='orange', linestyle='--', linewidth=WIDTH)
    ax.axvline(x=selections[lineNum][1] + 0.33, color='orange', linestyle='--', linewidth=WIDTH)
    
    ax.legend([a, b], ['Control', 'Treatment'])

def plotLinesPlt(lineNum, plt):
    a = plt.axvline(x=selections[lineNum][0], color='red', linestyle='--', linewidth=WIDTH)
    plt.axvline(x=selections[lineNum][0] + 0.33, color='red', linestyle='--', linewidth=WIDTH)
    
    b = plt.axvline(x=selections[lineNum][1], color='orange', linestyle='--', linewidth=WIDTH)
    plt.axvline(x=selections[lineNum][1] + 0.33, color='orange', linestyle='--', linewidth=WIDTH)
    
    plt.legend([a, b], ['Control', 'Treatment'])

#%% Plot Spectrogram

def plotSpectrogramEphys(line, obj, fr):
    
    
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
    
def plotCoherogram(lineNum, drug, eeg_signal, calcium_signal, fr): 

    

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
    
    
#%%

def computeStats(eeg, calcium, fr):
    eeg_power = computePower(eeg)
    calcium_power = computePower(calcium)
    xc, lag = computeXC(eeg, calcium, fr)
    coherence = computeCoherence(eeg, calcium, lag, fr)
    return [eeg_power, calcium_power, coherence, xc, lag]






#%%

def sliceSignal(signal, fr, slice_length=20):
    """
    Slices the signal into control and treatment segments based on time ranges.
    
    Args:
    - signal: The signal data to be sliced (assumes 1D array or list).
    - fr: Sampling frequency in Hz.
    - slice_length: Length of each slice in seconds.
    
    Returns:
    - sliced_control: The sliced portion of the signal for the control range.
    - sliced_treatment: The sliced portion of the signal for the treatment range.
    """
    
    # Convert slice length from seconds to sample indices
    slice_samples = int(slice_length * fr )  

    # Determine start indices for control and treatment
    control_start_idx = int(selections[lineNum][0] * fr * 60)
    treatment_start_idx = int(selections[lineNum][1] * fr * 60)
    
    # Extract slices from the signal
    sliced_control = signal[control_start_idx:control_start_idx + slice_samples]
    sliced_treatment = signal[treatment_start_idx:treatment_start_idx + slice_samples]
    
    return sliced_control, sliced_treatment

    

#%%

def computePower(signal):
    """
    Computes the power of a signal.
    
    Args:
    - signal: 1D array-like signal data.
    
    Returns:
    - power: Computed power of the signal.
    """
    power = np.sum(np.square(signal)) / len(signal)
    return power


def align_signals(signal1, signal2, lag, fr):
    """
    Aligns two signals based on a given lag.
    
    Args:
    - signal1: 1D array-like signal data (e.g., EEG).
    - signal2: 1D array-like signal data (e.g., calcium).
    - lag: Desired lag to align the signals (in seconds).
    - fr: Sampling frequency in Hz.
    
    Returns:
    - aligned_signal1: First signal (unaltered).
    - aligned_signal2: Second signal shifted by the lag.
    """
    shift_samples = int(lag * fr)
    
    if shift_samples > 0:
        aligned_signal1 = signal1[shift_samples:]  # Shift signal2 forward
        aligned_signal2 = signal2[:-shift_samples]
    elif shift_samples < 0:
        aligned_signal1 = signal1[:shift_samples]  # Shift signal1 forward
        aligned_signal2 = signal2[-shift_samples:]
    else:
        aligned_signal1 = signal1
        aligned_signal2 = signal2

    return aligned_signal1, aligned_signal2


def computeCoherence(signal1, signal2, ideal_lag, fr):
    """
    Computes coherence between two signals after aligning them by an ideal lag.
    
    Args:
    - signal1: 1D array-like signal data (e.g., EEG).
    - signal2: 1D array-like signal data (e.g., calcium).
    - ideal_lag: Desired lag to align the signals (in seconds).
    - fr: Sampling frequency in Hz (default is 1000 Hz).
    
    Returns:
    - mean_coherence: Mean coherence value across frequencies.
    """
    aligned_signal1, aligned_signal2 = align_signals(signal1, signal2, ideal_lag, fr)
    
    # Compute coherence using Welch's method
    f, Cxy = coherence(aligned_signal1, aligned_signal2, fs=fr)
    mean_coherence = np.mean(Cxy)
    
    return mean_coherence


#%%


def computeXC(eeg_signal, calcium_signal, fr, plot=True):
    """
    Plots the cross-correlation between EEG and calcium signals.
    
    Args:
    - eeg_signal: EEG signal data (1D array).
    - calcium_signal: Calcium signal data (1D array).
    - fr: Sampling frequency in Hz.
    
    Returns:
    - max_xc: Maximum cross-correlation value.
    - lag_at_max_xc: The lag corresponding to the maximum cross-correlation.
    """

    # normalize    
    norm_eeg = (eeg_signal - np.mean(eeg_signal)) / (np.std(eeg_signal)*len(eeg_signal))
    norm_calcium = (calcium_signal - np.mean(calcium_signal)) / np.std(calcium_signal)
    
    # Compute the cross-correlation and normalize by length
    nxcorr = correlate(norm_eeg, norm_calcium, mode='full')
    
    # Calculate the lags in seconds
    lags = correlation_lags(len(norm_eeg), len(norm_calcium), mode='full') / fr
    
    # Limit the lags and cross-correlation values to show only 20 seconds (±10 sec)
    max_display_lag = 10  # in seconds
    lag_mask = (lags >= -max_display_lag) & (lags <= max_display_lag)
    lags = lags[lag_mask]
    nxcorr = nxcorr[lag_mask]
    
    # Find the maximum cross-correlation and the lag at that point
    max_xc = np.max(nxcorr)
    lag_at_max_xc = lags[np.argmax(nxcorr)]
    
    if plot:
        # Plot the cross-correlation
        plt.figure(figsize=(10, 6))
        plt.plot(lags, nxcorr)
        plt.axvline(x=lag_at_max_xc, color='red', linestyle='--', 
                    label=f'Max Corr at {lag_at_max_xc:.2f} sec')
        plt.title("Cross-Correlation between EEG and Calcium Signals")
        plt.xlabel("Lag (seconds)")
        plt.ylabel("Cross-Correlation")
        plt.legend()
        plt.grid(True)
        
        plt.xlim([-10, 10])  # Set x-axis limits to show only 20 seconds total
        plt.show()
        
    return max_xc, lag_at_max_xc


    
    
    
    
    
    
    
    
    
    
    
    
    
    
    

#%% main

sleep_data, dex_data = [], []

for lineNum in lineNums:
    drug = number_to_drug.get(lineNum)
    meanFluorescenceFilePath = f'/Users/lukerichards/Desktop/Correlation Project/npzFiles/{drug}/meanFluorescence_{str(lineNum)}.npz'
    obj, fr, meanFluorescence = loadExperiment(lineNum, meanFluorescenceFilePath)
    
    # grab the signals
    eeg_signal = obj.fdata[0].data[obj.ephysIdxAllTTLEvents] # EEG signal
    calcium_signal = meanFluorescence['meanFluorescence']  # Calcium signal
    
    # plot comprehensive graphs
    plotSpectrogramEphys(lineNum, obj, fr)
    # missing miniscope spectrogram
    plotCoherogram(lineNum, drug, eeg_signal, calcium_signal, fr)
    
    #slice
    sliced_eeg, sliced_calcium = sliceSignal(eeg_signal, fr)
    
    # compute
    if (lineNum in data["sleep"]):
        sleep_data.append( computeStats(sliced_eeg, sliced_calcium, fr))
        
    elif (lineNum in data["dexmedetomidine"]):
        dex_data.append(computeStats(sliced_eeg, sliced_calcium, fr))
    
            
sleep_df = pd.DataFrame(sleep_data, columns=["EEG Power", "Calcium Power", "Coherence", "XC", "Lag"])
dex_df = pd.DataFrame(sleep_data, columns=["EEG Power", "Calcium Power", "Coherence", "XC", "Lag"])

print(sleep_df)
print(dex_df)

    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    


    

