import matplotlib.pyplot as plt  # Ensure Matplotlib is imported if not already
import numpy as np
import xarray as xr
from xrscipy.signal.spectral import coherogram
from scipy.signal import correlate, correlation_lags
from scipy.signal import coherence
import pandas as pd
from src import misc_functions
import os
from src.multitaper_spectrogram_python import multitaper_spectrogram
from src2.miniscope.miniscope_data_manager import MiniscopeDataManager
from src2.ephys.ephys_api import EphysAPI
from src2.ephys.ephys_data_manager import EphysDataManager
from src2.multimodal.miniscope_ephys_alignment_utils import sync_neuralynx_miniscope_timestamps, find_ephys_idx_of_TTL_events
import sys
sys.maxsize


#%% metadata
"""
line_num: dex dose
46: 0.0045 (high dose)
47: 0.0045
64: 0.0045
88: 0.0045
97: 0.0045
"""


line_nums = [46, 47, 64, 88, 97]
channel = 'PCvsPFCEEG'

data = {
    "dexmedetomidine": [46, 47, 64, 88, 97],
    "isoflurane": [91],
    "propofol": [104, 105, 107, 108],
    "sleep": [35, 83]
}

# Create a reverse mapping from numbers to drug types
number_to_drug = {num: drug for drug, numbers in data.items() for num in numbers}

#These times in minutes are filled in automatically in load_experiment
drug_infusion_start = {}






# Time range mapping for each line number as pairs of numbers
#time period in minutes
selections = {
    46:  [[1,20], [28.24, 83.24]],
    47:  [[1,20], [27.53, 82.24]],
    64:  [[1,20], [28.06, 83.06]],
    88:  [[1,20], [29, 84]],
    97:  [[1,20], [27.81, 82.81]],
}



#%% Load experiment 
def load_experiment(line_num, calcium_signal_filepath=None):
    print('Loading experiment...')
    
    #load miniscope data
    miniscope_data_manager = MiniscopeDataManager(line_num=line_num, filenames=[], auto_import_data=False)
    metadata = miniscope_data_manager._get_miniscope_metadata()
    if metadata: # fr defaults to 30fps if you don't have any miniscope experiments downloaded with metaData.json files in them
        miniscope_data_manager.metadata.update(metadata)
        fr = miniscope_data_manager.metadata['frameRate']
    else:
        fr = 30
    
    #load ephys data
    ephys_api = EphysAPI()
    ephys_api.run(line_num, channel_name=channel, remove_artifacts = False, filter_type = None, 
                  filter_range = [0.5, 4], plot_channel = False, plot_spectrogram = False, plot_phases = False, logging_level = "CRITICAL")
    channel_object = ephys_api.ephys_data_manager.get_channel(channel_name=channel)
    
    #updates drug_infusion_start above with when the anesthesia starts to be administered
    print()
    if number_to_drug[line_num] != 'sleep':
        for idx, label in enumerate(channel_object.events['labels']):
            if 'heat' in label:
                print(f"This is what it thinks the start drug time label is: {label}")
                start_time = channel_object.events['timestamps'][idx]
                drug_infusion_start[line_num] = start_time
                break
    
    
    #sync timestamps
    tCaIm, low_confidence_periods, channel_object, miniscope_data_manager = sync_neuralynx_miniscope_timestamps(channel_object, miniscope_data_manager, delete_TTLs=True, 
                                                                                               fix_TTL_gaps=False, only_experiment_events=True)
    ephys_idx_all_TTL_events, ephys_idx_ca_events = find_ephys_idx_of_TTL_events(tCaIm, channel=channel_object, frame_rate=fr, ca_events_idx=None, all_TTL_events=True)
    channel_object.signal = channel_object.signal[ephys_idx_all_TTL_events] # downsample
    
    channel_object.sampling_rate = np.array(fr)
    if calcium_signal_filepath:
        miniscope_data_manager.mean_fluorescence_dict = np.load(calcium_signal_filepath)
    return channel_object, miniscope_data_manager, fr
    

#%% Plot lines
WIDTH = 0.5

def plot_lines_ax(line_num, ax):
    "The two functions in this cell help to draw lines on graphs to mark different events"
    
    a = ax.axvline(x=selections[line_num][0][0], color='red', linestyle='--', linewidth=WIDTH)
    ax.axvline(x=selections[line_num][0][0] + 0.33, color='red', linestyle='--', linewidth=WIDTH)
    x = ax.axvline(x=selections[line_num][0][1], color='red', linestyle='--', linewidth=WIDTH)
    ax.axvline(x=selections[line_num][0][1] + 0.33, color='red', linestyle='--', linewidth=WIDTH)
    
    b = ax.axvline(x=selections[line_num][1][0], color='orange', linestyle='--', linewidth=WIDTH)
    ax.axvline(x=selections[line_num][1][0] + 0.33, color='orange', linestyle='--', linewidth=WIDTH)
    y = ax.axvline(x=selections[line_num][1][1], color='orange', linestyle='--', linewidth=WIDTH)
    ax.axvline(x=selections[line_num][1][1] + 0.33, color='orange', linestyle='--', linewidth=WIDTH)
    
    if number_to_drug[line_num] != 'sleep':
        c =  ax.axvline(x=drug_infusion_start[line_num]/60, color='red', linestyle='-', linewidth=1)
        ax.axvline(x=drug_infusion_start[line_num]/60, color='red', linestyle='-', linewidth=1)
        ax.legend([a, b, c], ['Control', 'Treatment', 'Start of Drug Infusion'])
    else:
        ax.legend([a, b], ['Control', 'Treatment'])

def plot_lines_plt(line_num, plt):
    a = plt.axvline(x=selections[line_num][0][0], color='red', linestyle='--', linewidth=WIDTH)
    plt.axvline(x=selections[line_num][0][0] + 0.33, color='red', linestyle='--', linewidth=WIDTH)
    x = plt.axvline(x=selections[line_num][0][1], color='red', linestyle='--', linewidth=WIDTH)
    plt.axvline(x=selections[line_num][0][1] + 0.33, color='red', linestyle='--', linewidth=WIDTH)
    
    b = plt.axvline(x=selections[line_num][1][0], color='orange', linestyle='--', linewidth=WIDTH)
    plt.axvline(x=selections[line_num][1][0] + 0.33, color='orange', linestyle='--', linewidth=WIDTH)
    b = plt.axvline(x=selections[line_num][1][1], color='orange', linestyle='--', linewidth=WIDTH)
    plt.axvline(x=selections[line_num][1][1] + 0.33, color='orange', linestyle='--', linewidth=WIDTH)
    
    if number_to_drug[line_num] != 'sleep':
        c =  plt.axvline(x=drug_infusion_start[line_num]/60, color='red', linestyle='-', linewidth=1)
        plt.axvline(x=drug_infusion_start[line_num]/60, color='red', linestyle='-', linewidth=1)
        plt.legend([a, b, c], ['Control', 'Treatment', 'Start of Drug Infusion'])
    else:
        plt.legend([a, b], ['Control', 'Treatment'])
 

    
    
#%% Plot Coherogram
    
def plot_coherogram(line_num, drug, eeg_signal, calcium_signal, fr): 
    """Plots the coherogram of two signals"""
    

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
    plt.title(f"Coherogram {drug} line {line_num}")
    plt.xlabel("Time (minutes)")
    plt.ylabel("Frequency (Hz)")
    
    plt.legend()

    plot_lines_plt(line_num, plt)

    
    plt.show()
    
    
#%%

def compute_stats(eeg_signal, calcium_signal, line, exp_type, fr):
    """High level function that computes the various statistics of our two signals"""
    
    eeg_power = compute_power(line, fr, eeg_signal, windowLength=60, plotSpectrogram=False)
    calcium_power = compute_power(line, fr, calcium_signal, windowLength=60, plotSpectrogram=False)
    xc, lag = compute_xc(eeg_signal, calcium_signal, line, exp_type, fr)
    coherence = compute_coherence(eeg_signal, calcium_signal, lag, fr)
    return [eeg_power, calcium_power, coherence, xc, lag]






#%%
def plot_signal_with_slices(signal, line_num, title="No title"):
    """This function plots the full signal with the slices in selections shaded with red and blue"""
    
    # Slice the signal into control and treatment segments
    sliced_control, sliced_treatment = slice_signal(signal, line_num, fr)
    
    # Create time arrays for plotting (in minutes)
    total_samples = len(signal)
    time_full = np.arange(total_samples) / (fr * 60)  # Convert samples to minutes
    
    # Get the start and end indices for control and treatment from slice_signal
    control_start_idx = int(selections[line_num][0][0] * fr * 60)  # Start of control (samples)
    control_end_idx = int(selections[line_num][0][1] * fr * 60)    # End of control (samples)
    treatment_start_idx = int(selections[line_num][1][0] * fr * 60) # Start of treatment (samples)
    treatment_end_idx = int(selections[line_num][1][1] * fr * 60)   # End of treatment (samples)
    
    # Create time arrays for control and treatment segments
    time_control = np.arange(control_start_idx, control_end_idx) / (fr * 60)  # Time for control segment
    time_treatment = np.arange(treatment_start_idx, treatment_end_idx) / (fr * 60)  # Time for treatment segment
    
    # Create the plot
    plt.figure(figsize=(12, 6))
    
    # Plot the original signal
    plt.plot(time_full, signal, color='gray', label='Original Signal', alpha=0.5)
    
    # Overlay the control segment
    plt.plot(time_control, sliced_control, color='blue', label='Control Segment', linewidth=2)
    
    # Overlay the treatment segment
    plt.plot(time_treatment, sliced_treatment, color='red', label='Treatment Segment', linewidth=2)
    
    # Add labels, title, and legend
    plt.xlabel('Time (minutes)')
    plt.ylabel('Signal Amplitude')
    plt.title(f'{title} Signal with Control and Treatment Segments (Line {line_num})')
    plt.legend()
    plt.grid(True)
    
    # Show the plot
    plt.show()



def slice_signal(signal, line_num, fr):
    """
    Slices the signal into control and treatment segments based on time ranges.
    
    Args:
    - signal: The signal data to be sliced (assumes 1D array or list).
    - fr: Sampling frequency in Hz.
    
    Returns:
    - sliced_control: The sliced portion of the signal for the control range.
    - sliced_treatment: The sliced portion of the signal for the treatment range.
    """

    # Determine start indices for control and treatment
    control_start_idx = int(selections[line_num][0][0] * fr * 60)
    control_end_idx = int(selections[line_num][0][1] * fr * 60)
    treatment_start_idx = int(selections[line_num][1][0] * fr * 60)
    treatment_end_idx = int(selections[line_num][1][1] * fr * 60)
    
    # Extract slices from the signal
    sliced_control = signal[control_start_idx:control_end_idx]
    sliced_treatment = signal[treatment_start_idx:treatment_end_idx]
    
    return sliced_control, sliced_treatment

#%%



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


def compute_coherence(signal1, signal2, ideal_lag, fr):
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


def compute_xc(eeg_signal, calcium_signal, line, exp_type, fr, plot=True):
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
    max_xc = nxcorr[np.argmax(nxcorr)]
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


    
    
    
    
    
    
#%%
    
def filter_frequency(eeg_signal, calcium_signal, fr, cut):
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
    filtered_calcium_signal = misc_functions.filterData(calcium_signal, n=2, cut=cut, ftype='butter', btype='bandpass', fs=fr)
    filtered_eeg_signal = EphysDataManager._filter_data(data=eeg_signal, n=2, cut=cut, ftype='butter', fs=fr, btype='bandpass', bodePlot=False)
    
    return filtered_eeg_signal, filtered_calcium_signal
    
#%%
    
    
def compute_power(line, fr, data=None, windowLength=30, windowStep=3, freqLims=[0,20], timeBandwidth=2, plotSpectrogram=True, plot_mean_power=False, title="No title"):
    """Estimate (and plot) the multi-taper spectrogram (of the mean miniscope fluorescence). Developed with Mike Prerau's function."""
    print('Computing spectrogram of average miniscope fluorescence...')
    # Set spectrogram params
    fs = fr
    numTapers = timeBandwidth * 2 - 1
    windowParams = [windowLength, windowStep]
    minNfft = 0  # No minimum nfft
    detrendOpt = 'constant'  # detrend each window by subtracting the average
    multiprocess = True  # use multiprocessing
    nJobs = 3  # use 3 cores in multiprocessing
    weighting = 'unity'  # weight each taper at 1
    plotOn = False  # plot spectrogram using multitaper_spectrogram()
    returnFig = False  # do not return plotted spectrogram
    climScale = False # do not auto-scale colormap
    verbose = True  # print extra info
    xyflip = False  # do not transpose spect output matrix
    
    # Compute the multitaper spectrogram and convert the output to decibels
    power_matrix, times, frequencies = multitaper_spectrogram(data, fs, freqLims, timeBandwidth, numTapers, windowParams, minNfft, detrendOpt, multiprocess, nJobs, weighting, plotOn, returnFig, climScale, verbose, xyflip)
    power_array = 10 * np.log10(power_matrix) # convert to decibels
    
    low_freq = 0.5
    high_freq = 4.0

    # Find indices corresponding to the desired frequency band
    freq_indices = np.where((frequencies >= low_freq) & (frequencies <= high_freq))[0]
    
    print(f"power_array: {power_array.shape}")
    print(f"frequency_array: {frequencies.shape}")
    print(f"indices: {freq_indices}")

    
    # Slice the spectral power array for the desired frequency band
    mean= 0
    sliced_power_array = power_array[freq_indices]      
    mean = np.mean(sliced_power_array)
    
    if plot_mean_power: 
        plot_mean_power_across_time(sliced_power_array, times, line, title)
    
    # Plot the multitaper spectrogram
    if plotSpectrogram:
        h, ax = misc_functions.spectrogram(times/60, frequencies, power_array, xLabel='Time (min)')
        plt.figure(figsize=(10,6))
        
        # Add title with line number and associated drug
        drug = number_to_drug.get(line, "Unknown")
            
        ax.set_title(f"{title} | Line Number: {line} | Drug: {drug}", fontsize=9)
        
        # Plot red lines using the mapping
        plot_lines_ax(line, ax)
        

        plt.tight_layout()
        plt.show()  # Display the graph
    
    return float(mean)


def plot_mean_power_across_time(sliced_power_array, times, line_num, title):
    """Plot the mean power array with the sliced signals we will be taking overlapped
    This function is called by the function above, as it needs the power matrix of the signal to be computed
    """
    mean_power_across_time = np.mean(sliced_power_array, axis=0)
    
    
    # For spectrogram data, use time points to find closest indices
    control_start_time = selections[line_num][0][0] * 60  # Convert minutes to seconds
    control_end_time = selections[line_num][0][1] * 60    # Convert minutes to seconds
    treatment_start_time = selections[line_num][1][0] * 60  # Convert minutes to seconds
    treatment_end_time = selections[line_num][1][1] * 60    # Convert minutes to seconds
    
    # Find indices in spectrogram_times closest to the desired times
    control_start_idx = np.argmin(np.abs(times - control_start_time))
    control_end_idx = np.argmin(np.abs(times - control_end_time))
    treatment_start_idx = np.argmin(np.abs(times - treatment_start_time))
    treatment_end_idx = np.argmin(np.abs(times - treatment_end_time))

    # Slice the signal into control and treatment segments
    sliced_control = mean_power_across_time[control_start_idx:control_end_idx]
    sliced_treatment = mean_power_across_time[treatment_start_idx:treatment_end_idx]
    
    # Create time arrays for plotting (in minutes)
    time_full = times / 60  # Convert spectrogram times (in seconds) to minutes
    
    # Create time arrays for control and treatment segments
    time_control = times[control_start_idx:control_end_idx] / 60  # Convert to minutes
    time_treatment = times[treatment_start_idx:treatment_end_idx] / 60  # Convert to minutes
    
    # Create the plot
    plt.figure(figsize=(12, 6))
    
    # Plot the original signal
    plt.plot(time_full, mean_power_across_time, color='gray', label='Original Signal', alpha=0.5)
    
    # Overlay the control segment if not empty
    if len(sliced_control) > 0 and len(time_control) > 0:
        plt.plot(time_control, sliced_control, color='blue', label='Control Segment', linewidth=2)
    else:
        print(f"Warning: Control segment is empty for line {line_num}")
    
    # Overlay the treatment segment if not empty
    if len(sliced_treatment) > 0 and len(time_treatment) > 0:
        plt.plot(time_treatment, sliced_treatment, color='red', label='Treatment Segment', linewidth=2)
    else:
        print(f"Warning: Treatment segment is empty for line {line_num}")
    
    # Add labels, title, and legend
    plt.xlabel('Time (minutes)')
    plt.ylabel('Signal Amplitude (dB)')
    plt.title(f'{title} Signal of mean slow wave power (Line {line_num})')
    plt.legend()
    plt.grid(True)
    
    # Show the plot
    plt.show()
    plt.close()
    
    



#%% main

# Initialize data lists
sleep_data, dex_data, iso_data, prop_data = [], [], [], []
rows = ["EEG Power", "Calcium Power", "Coherence", "XC", "Lag"]

for line in line_nums:
    print(f'Running line number: {line}')
    drug = number_to_drug.get(line)
    calcium_signal_filepath = f'/Users/nathan/Desktop/meanFluorescence/meanFluorescence_{str(line)}.npz'
    channel_object, miniscope_data_manager, fr = load_experiment(line, calcium_signal_filepath)
    
    # Grab the signals
    eeg_signal = channel_object.signal
    calcium_signal = miniscope_data_manager.mean_fluorescence_dict['meanFluorescence']
    
    #plot both entire signals with the slices that are stored in selections overlapped
    plot_signal_with_slices(eeg_signal, line, title="Ephys")
    plot_signal_with_slices(calcium_signal, line, title="Miniscope")
    
    # Plot ephys spectrogram and mean power signal
    compute_power(line, fr, channel_object.signal, plot_mean_power=True, title="Ephys")
    #Plot just calcium spectrogram
    compute_power(line, fr, calcium_signal, plot_mean_power=False, title="Miniscope")
    #Plot coherence of both signals
    plot_coherogram(line, drug, eeg_signal, calcium_signal, fr)
    
    # Slice signals into small segments to use for data analysis
    control_eeg, treatment_eeg = slice_signal(eeg_signal, line, fr)
    control_calcium, treatment_calcium = slice_signal(calcium_signal, line, fr)
    
    #Filter the control/treatment signals
    CUT = [0.5,4]
    filtered_control_calcium, filtered_control_eeg = filter_frequency(control_eeg, control_calcium, fr, cut=CUT)
    filtered_treatment_calcium, filtered_treatment_eeg = filter_frequency(treatment_eeg, treatment_calcium, fr, cut=CUT)
 
    
    # Compute stats for control and treatment
    control_list = compute_stats(filtered_control_eeg, filtered_control_calcium, line, "Control", fr)
    treatment_list = compute_stats(filtered_treatment_eeg, filtered_treatment_calcium, line, "Treatment", fr)
    
    # Compute the ratio for each pair of control and treatment values    
    ratios = []
    
    for control, treatment in zip(control_list, treatment_list):
        if abs(control) < 1e-10:  # Use a small threshold instead of int(control)
            ratios.append(np.nan)  # Use NaN for invalid ratios
        else:
            ratios.append(treatment / control)
    
    # Combine into a row with columns ["lineNum", "Control", "Treatment", "Ratio"]
    combined_data = {
        "line_num": [line] * len(rows),
        "Measurement": rows,
        "Control": control_list,
        "Treatment": treatment_list,
        "Ratio": ratios
    }
    
    # Convert to DataFrame row format and append to appropriate list
    row_df = pd.DataFrame(combined_data)
    

    if line in data["dexmedetomidine"]:
        dex_data.append(row_df)

# Combine all rows into final DataFrames

dex_df = pd.concat(dex_data, ignore_index=True)

# Function to compute mean ± std for each measurement
def compute_mean_std(df):
    result = df.groupby("Measurement")[["Control", "Treatment", "Ratio"]].agg(
        ["mean", "std"]
    ).reset_index()
    return result


# Compute averaged DataFrames

dex_avg_df = compute_mean_std(dex_df)

print(f"Control: {control_list}, Treatment: {treatment_list}, Ratios: {ratios}")


#Print the resulting DataFrames

#print("\nSleep DataFrame:")
#print(sleep_df)

print("\nDexmedetomidine DataFrame:")
print(dex_df)

#print("\nIsoflurane DataFrame:")
#print(iso_df)

#print("\nPropofol DataFrame:")
#print(prop_df)

#print("\nAveraged Sleep DataFrame (Mean ± Std):")
#print(sleep_avg_df)

print("\nAveraged Dexmedetomidine DataFrame (Mean ± Std):")
print(dex_avg_df)

#print("\nAveraged Isoflurane DataFrame (Mean ± Std):")
#print(iso_avg_df)

#print("\nAveraged Propofol DataFrame (Mean ± Std):")
#print(prop_avg_df)




# Create directory for results if it doesn't exist
results_dir = os.path.join(os.pardir, "Poster Results")
os.makedirs(results_dir, exist_ok=True)

# Save DataFrames as CSV files
#sleep_df.to_csv(os.path.join(results_dir, "sleep_data.csv"), index=False)
dex_df.to_csv(os.path.join(results_dir, "dex_data.csv"), index=False)
#sleep_avg_df.to_csv(os.path.join(results_dir, "sleep_avg_data.csv"), index=False)
dex_avg_df.to_csv(os.path.join(results_dir, "dex_avg_data.csv"), index=False)

#print(f"DataFrames saved to '{results_dir}' directory.")
    
    
    
    
    

    
