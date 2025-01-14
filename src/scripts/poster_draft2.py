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
import os


#%% metadata

lineNums = [35, 37, 38, 83, 90, 92, 46, 47, 101, 97, 64, 88]
channel = 'PFCLFPvsCBEEG'

data = {
    "sleep": [37, 38, 83, 90, 92, 35],
    "dexmedetomidine": [46, 47, 101, 97, 64, 88],
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

def computeStats(eeg, calcium, line, exp_type, fr):
    eeg_power = computePower(eeg)
    calcium_power = computePower(calcium)
    xc, lag = computeXC(eeg, calcium, line, exp_type, fr)
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


def computeXC(eeg_signal, calcium_signal, line, exp_type, fr, plot=True):
    print(f"line: {line}, exp_type: {exp_type}")

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
    
    # Find the maximum absolute cross-correlation and the lag at that point
    max_xc = nxcorr[np.argmax(np.abs(nxcorr))]
    lag_at_max_xc = lags[np.argmax(nxcorr)]
    
    if plot:
        # Plot the cross-correlation
        plt.figure(figsize=(10, 6))
        plt.plot(lags, nxcorr)
        
        # Mark the lag at maximum cross-correlation
        plt.axvline(x=lag_at_max_xc, color='red', linestyle='--', 
                    label=f'Max Corr at {lag_at_max_xc:.2f} sec')
        
        # Titles and labels
        plt.title(f"Cross-Correlation | Line {line} | {number_to_drug[line]} | {exp_type}")
        plt.xlabel("Lag (seconds)")
        plt.ylabel("Cross-Correlation")
        plt.legend()
        plt.grid(True)
        
        # Set axis limits
        plt.xlim([-10, 10])  # Show 20 seconds total on x-axis
        plt.ylim([-0.6, 0.6])  # Standardize y-axis scale
        
        plt.show()

        
    return max_xc, lag_at_max_xc


    
    
    
    
    
    
    
    
    
    
    
    
    
    
    

#%% main

# Initialize data lists
sleep_data, dex_data = [], []
rows = ["EEG Power", "Calcium Power", "Coherence", "XC", "Lag"]

for lineNum in lineNums:
    drug = number_to_drug.get(lineNum)
    meanFluorescenceFilePath = f'/Users/lukerichards/Desktop/Correlation Project/npzFiles/{drug}/meanFluorescence_{str(lineNum)}.npz'
    obj, fr, meanFluorescence = loadExperiment(lineNum, meanFluorescenceFilePath)
    
    # Grab the signals
    eeg_signal = obj.fdata[0].data[obj.ephysIdxAllTTLEvents]
    calcium_signal = meanFluorescence['meanFluorescence']
    
    # Plot comprehensive graphs
    plotSpectrogramEphys(lineNum, obj, fr)
    plotCoherogram(lineNum, drug, eeg_signal, calcium_signal, fr)
    
    # Slice signals
    control_eeg, treatment_eeg = sliceSignal(eeg_signal, fr)
    control_calcium, treatment_calcium = sliceSignal(calcium_signal, fr)
    
    # Compute stats for control and treatment
    control_list = computeStats(control_eeg, control_calcium, lineNum, "Control", fr)
    treatment_list = computeStats(treatment_eeg, treatment_calcium, lineNum, "Treatment", fr)
    
    # Compute the ratio for each pair of control and treatment values
    ratios = [ctrl / treat if treat != 0 else float('nan') for ctrl, treat in zip(control_list, treatment_list)]
    
    # Combine into a row with columns ["lineNum", "Control", "Treatment", "Ratio"]
    combined_data = {
        "lineNum": [lineNum] * len(rows),
        "Measurement": rows,
        "Control": control_list,
        "Treatment": treatment_list,
        "Ratio": ratios
    }
    
    # Convert to DataFrame row format and append to appropriate list
    row_df = pd.DataFrame(combined_data)
    
    if lineNum in data["sleep"]:
        sleep_data.append(row_df)
    elif lineNum in data["dexmedetomidine"]:
        dex_data.append(row_df)

# Combine all rows into final DataFrames for sleep and dexmedetomidine
sleep_df = pd.concat(sleep_data, ignore_index=True)
dex_df = pd.concat(dex_data, ignore_index=True)

# Function to compute mean ± std for each measurement
def compute_mean_std(df):
    result = df.groupby("Measurement")[["Control", "Treatment", "Ratio"]].agg(
        lambda x: f"{x.mean():.2f} ± {x.std():.2f}"
    )
    return result.reset_index()

# Compute averaged DataFrames for sleep and dexmedetomidine
sleep_avg_df = compute_mean_std(sleep_df)
dex_avg_df = compute_mean_std(dex_df)

# Print the resulting DataFrames
print("Sleep DataFrame:")
print(sleep_df)

print("\nDexmedetomidine DataFrame:")
print(dex_df)

print("\nAveraged Sleep DataFrame (Mean ± Std):")
print(sleep_avg_df)

print("\nAveraged Dexmedetomidine DataFrame (Mean ± Std):")
print(dex_avg_df)

# Create directory for results if it doesn't exist
results_dir = os.path.join(os.pardir, "Poster Results")
os.makedirs(results_dir, exist_ok=True)

# Save DataFrames as CSV files
sleep_df.to_csv(os.path.join(results_dir, "sleep_data.csv"), index=False)
dex_df.to_csv(os.path.join(results_dir, "dex_data.csv"), index=False)
sleep_avg_df.to_csv(os.path.join(results_dir, "sleep_avg_data.csv"), index=False)
dex_avg_df.to_csv(os.path.join(results_dir, "dex_avg_data.csv"), index=False)

print(f"DataFrames saved to '{results_dir}' directory.")






# NOTES

# need to include before AND after stats...
    

# lables on cross correlation graphs
# Update dataframe to be as eric proposed
# make XC charts a standard scale from -0.4 - 0.4
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    


    

